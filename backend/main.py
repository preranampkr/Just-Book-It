"""
FastAPI Backend for Just Book It — Hands-Free Voice Assistant.
Milestone 1: No Screens Theme.
Supports both Google Cloud services and browser Web Speech API.
"""

import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from speech_service import SpeechService, SUPPORTED_LANGUAGES
from gemini_service import GeminiService
from tts_service import TTSService, WELCOME_MESSAGES
from voice_service import VoiceService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("just_book_it")

app = FastAPI(
    title="Just Book It — Hands-Free Voice Travel Assistant",
    version="1.0.0",
    description="Backend API for Milestone 1: Voice-First Travel Planning Assistant",
)

# CORS Middleware for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
speech_service = SpeechService()
gemini_service = GeminiService()
tts_service = TTSService()
voice_service = VoiceService(
    speech_service=speech_service,
    gemini_service=gemini_service,
    tts_service=tts_service,
)


class ChatTurnPayload(BaseModel):
    transcript: str
    conversation_id: Optional[str] = None
    language_code: Optional[str] = "en-IN"


@app.get("/health")
async def health_check():
    """
    Returns backend health and integration configuration status
    without exposing credentials.
    """
    gemini_configured = bool(os.environ.get("GEMINI_API_KEY"))
    google_creds_configured = bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        and os.path.exists(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
    )
    configured_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    return {
        "status": "healthy",
        "service": "Just Book It Voice Assistant",
        "integrations": {
            "gemini": {
                "configured": gemini_configured,
                "model": configured_model,
                "client_ready": gemini_service.is_available,
            },
            "speech_to_text": {
                "provider": "google-cloud" if speech_service.is_available else "browser-web-speech",
                "google_cloud_configured": google_creds_configured and speech_service.is_available,
                "client_ready": True,
                "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
            },
            "text_to_speech": {
                "provider": "google-cloud" if tts_service.is_available else "browser-speech-synthesis",
                "google_cloud_configured": google_creds_configured and tts_service.is_available,
                "client_ready": True,
                "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
            },
        },
    }


@app.get("/api/welcome-audio")
async def get_welcome_audio(language_code: str = Query("en-IN")):
    """
    Returns the welcome text and optional synthesized audio for initial onboarding.
    If GCP TTS is not active, audio_base64 is null and frontend speaks via browser speechSynthesis.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        language_code = "en-IN"

    welcome_text = WELCOME_MESSAGES.get(language_code, WELCOME_MESSAGES["en-IN"])
    audio_base64 = None
    audio_format = None

    if tts_service.is_available:
        try:
            _, audio_bytes, audio_format = tts_service.get_welcome_audio(language_code)
            import base64
            audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
        except Exception as e:
            logger.info(f"Welcome audio TTS fallback to browser: {e}")

    return {
        "language_code": language_code,
        "welcome_text": welcome_text,
        "audio_base64": audio_base64,
        "audio_format": audio_format,
    }


@app.post("/api/chat-turn")
async def chat_turn(payload: ChatTurnPayload):
    """
    Processes a conversational turn from browser Speech Recognition:
    - Interprets intent and contextual travel planning (Gemini)
    - Preserves multi-turn session history
    - Returns response text for browser speech synthesis
    """
    lang = payload.language_code or "en-IN"
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{lang}' not supported. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
        )

    try:
        result = voice_service.process_text_turn(
            transcript=payload.transcript,
            conversation_id=payload.conversation_id,
            language_code=lang,
        )
        return JSONResponse(content=result)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))
    except Exception as e:
        logger.exception("Error processing chat turn")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-turn")
async def voice_turn(
    audio: Optional[UploadFile] = File(None, description="16kHz mono WAV audio file"),
    transcript: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    language_code: str = Form("en-IN"),
):
    """
    Dual-mode voice turn endpoint:
    - If transcript is passed (from browser Speech Recognition), routes to text processing.
    - If audio file is passed, validates and transcribes via speech_service.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{language_code}' not supported. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
        )

    # Mode 1: Direct transcript
    if transcript is not None and transcript.strip():
        result = voice_service.process_text_turn(
            transcript=transcript,
            conversation_id=conversation_id,
            language_code=language_code,
        )
        return JSONResponse(content=result)

    # Mode 2: Audio file
    if audio is None:
        raise HTTPException(status_code=400, detail="Either audio file or transcript must be provided.")

    try:
        audio_content = await audio.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read audio payload: {str(e)}")

    if not audio_content:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")

    try:
        result = voice_service.process_voice_turn(
            audio_bytes=audio_content,
            conversation_id=conversation_id,
            language_code=language_code,
        )
        return JSONResponse(content=result)
    except ValueError as ve:
        logger.warning(f"Voice turn validation error: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"Voice turn runtime error: {re}")
        raise HTTPException(status_code=502, detail=str(re))
    except Exception as e:
        logger.exception("Unexpected error during voice turn processing")
        raise HTTPException(status_code=500, detail=f"Internal voice processing error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)

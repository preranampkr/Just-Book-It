"""
Voice Service for Just Book It.
Orchestrates speech recognition, Gemini intelligence, session management, and speech synthesis.
Supports both Google Cloud STT/TTS and browser-based Web Speech API.
"""

import time
import uuid
import base64
import logging
from typing import Dict, Any, Optional

from speech_service import SpeechService
from gemini_service import GeminiService
from tts_service import TTSService

logger = logging.getLogger(__name__)

# Max messages retained in conversational history per session
MAX_SESSION_HISTORY = 20

# Command phrases for hands-free control
PAUSE_COMMANDS = {
    "pause listening", "pause", "stop listening", "सुनना रोकें", "ವಿರಾಮ", "ನಿಲ್ಲಿಸಿ"
}
RESUME_COMMANDS = {
    "resume listening", "resume", "continue", "शुरू करें", "ಮುಂದುವರಿಸಿ"
}

# Spoken language switch triggers
LANGUAGE_SWITCH_TRIGGERS = {
    "hindi": "hi-IN",
    "हिंदी": "hi-IN",
    "kannada": "kn-IN",
    "ಕನ್ನಡ": "kn-IN",
    "english": "en-IN",
    "अंग्रेजी": "en-IN",
    "ಇಂಗ್ಲಿಷ್": "en-IN",
}


class VoiceService:
    def __init__(
        self,
        speech_service: SpeechService,
        gemini_service: GeminiService,
        tts_service: TTSService,
    ):
        self.speech_service = speech_service
        self.gemini_service = gemini_service
        self.tts_service = tts_service
        # In-memory session store: conversation_id -> session dict
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_or_create_session(
        self, conversation_id: Optional[str] = None, language_code: str = "en-IN"
    ) -> tuple[str, Dict[str, Any]]:
        """Retrieves an existing session or initializes a fresh one."""
        if not conversation_id or conversation_id not in self._sessions:
            new_id = conversation_id if conversation_id else str(uuid.uuid4())
            self._sessions[new_id] = {
                "id": new_id,
                "language": language_code,
                "history": [],
                "created_at": time.time(),
                "last_active": time.time(),
                "state": "active",
            }
            logger.info(f"Created new conversation session: {new_id} (Language: {language_code})")
            return new_id, self._sessions[new_id]

        session = self._sessions[conversation_id]
        session["last_active"] = time.time()
        if language_code:
            session["language"] = language_code
        return conversation_id, session

    def _try_synthesize_tts(self, text: str, lang: str) -> tuple[Optional[str], Optional[str]]:
        """Attempts to synthesize audio using Google Cloud TTS if available, else returns (None, None)."""
        if self.tts_service and self.tts_service.is_available:
            try:
                audio_bytes, mime_type = self.tts_service.synthesize(text, language_code=lang)
                return base64.b64encode(audio_bytes).decode("ascii"), mime_type
            except Exception as e:
                logger.info(f"GCP TTS not active or unavailable ({e}); client will use browser speechSynthesis.")
        return None, None

    def process_text_turn(
        self,
        transcript: str,
        conversation_id: Optional[str] = None,
        language_code: str = "en-IN",
    ) -> Dict[str, Any]:
        """
        Executes a single conversational turn with an input transcript:
        1. Validates transcript
        2. Detects control commands (pause / stop / switch language)
        3. Queries Gemini with conversation history
        4. Synthesizes audio if GCP TTS is available (or leaves for browser speechSynthesis)
        5. Updates session history
        """
        conv_id, session = self.get_or_create_session(conversation_id, language_code)
        lang = session.get("language", language_code)
        transcript_clean = transcript.strip().lower()

        # Handle empty utterances
        if not transcript_clean:
            fallback_prompts = {
                "en-IN": "I didn't catch that. Could you please say that again?",
                "hi-IN": "माफ़ कीजिए, मैं सुन नहीं सका। क्या आप फिर से कह सकते हैं?",
                "kn-IN": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಬಹುದೇ?",
            }
            msg = fallback_prompts.get(lang, fallback_prompts["en-IN"])
            audio_b64, mime_type = self._try_synthesize_tts(msg, lang)
            return {
                "conversation_id": conv_id,
                "transcript": "",
                "response_text": msg,
                "audio_base64": audio_b64,
                "audio_format": mime_type,
                "action": "continue",
                "language_code": lang,
            }

        # Check for spoken control commands
        if any(cmd in transcript_clean for cmd in PAUSE_COMMANDS):
            pause_responses = {
                "en-IN": "Listening is paused. Say resume or click the screen when you are ready to continue.",
                "hi-IN": "सुनना रोक दिया गया है। जब आप तैयार हों, तब 'शुरू करें' बोलें।",
                "kn-IN": "ಆಲಿಸುವಿಕೆಯನ್ನು ವಿರಾಮಗೊಳಿಸಲಾಗಿದೆ. ಮುಂದುವರಿಸಲು ಸಿದ್ಧರಾದಾಗ 'ಮುಂದುವರಿಸಿ' ಎಂದು ಹೇಳಿ.",
            }
            resp_text = pause_responses.get(lang, pause_responses["en-IN"])
            session["state"] = "paused"
            audio_b64, mime_type = self._try_synthesize_tts(resp_text, lang)
            return {
                "conversation_id": conv_id,
                "transcript": transcript,
                "response_text": resp_text,
                "audio_base64": audio_b64,
                "audio_format": mime_type,
                "action": "pause",
                "language_code": lang,
            }

        # Check for spoken language switch
        for trigger, target_lang in LANGUAGE_SWITCH_TRIGGERS.items():
            if trigger in transcript_clean and (
                "switch to" in transcript_clean
                or "change to" in transcript_clean
                or "speak in" in transcript_clean
                or len(transcript_clean.split()) <= 2
            ):
                lang = target_lang
                session["language"] = target_lang
                confirmations = {
                    "en-IN": "Switched to English. How can I help with your travel plans?",
                    "hi-IN": "हिंदी भाषा चुन ली गई है। अपनी यात्रा की योजना के लिए बताइए, मैं क्या मदद करूँ?",
                    "kn-IN": "ಕನ್ನಡ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಲಾಗಿದೆ. ನಿಮ್ಮ ಪ್ರವಾಸ ಯೋಜನೆಗೆ ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
                }
                resp_text = confirmations.get(lang, confirmations["en-IN"])
                audio_b64, mime_type = self._try_synthesize_tts(resp_text, lang)
                return {
                    "conversation_id": conv_id,
                    "transcript": transcript,
                    "response_text": resp_text,
                    "audio_base64": audio_b64,
                    "audio_format": mime_type,
                    "action": "continue",
                    "language_code": lang,
                }

        # Query Gemini with conversation history
        history = session.get("history", [])
        response_text = self.gemini_service.generate_response(
            user_message=transcript,
            conversation_history=history,
            language_code=lang,
        )

        # Update session history
        history.append({"role": "user", "content": transcript})
        history.append({"role": "assistant", "content": response_text})
        if len(history) > MAX_SESSION_HISTORY:
            session["history"] = history[-MAX_SESSION_HISTORY:]
        else:
            session["history"] = history

        # Synthesize audio if GCP TTS is available
        audio_b64, mime_type = self._try_synthesize_tts(response_text, lang)

        return {
            "conversation_id": conv_id,
            "transcript": transcript,
            "response_text": response_text,
            "audio_base64": audio_b64,
            "audio_format": mime_type,
            "action": "continue",
            "language_code": lang,
        }

    def process_voice_turn(
        self,
        audio_bytes: bytes,
        conversation_id: Optional[str] = None,
        language_code: str = "en-IN",
    ) -> Dict[str, Any]:
        """Processes an audio utterance via SpeechService, then delegates to process_text_turn."""
        conv_id, session = self.get_or_create_session(conversation_id, language_code)
        lang = session.get("language", language_code)

        transcript = self.speech_service.transcribe(audio_bytes, language_code=lang)
        return self.process_text_turn(
            transcript=transcript,
            conversation_id=conv_id,
            language_code=lang,
        )

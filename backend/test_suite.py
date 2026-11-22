"""
Comprehensive Test Suite for Just Book It — Hands-Free Voice Assistant.
Tests API endpoints, session continuity, voice service coordination, audio validation,
and language routing for English, Hindi, and Kannada.
"""

import io
import wave
import struct
import math
import pytest
from fastapi.testclient import TestClient

from main import app
from voice_service import VoiceService
from speech_service import SpeechService
from gemini_service import GeminiService
from tts_service import TTSService


def create_synthetic_wav(duration_sec: float = 1.0, sample_rate: int = 16000, freq_hz: float = 440.0) -> bytes:
    """Generates a valid 16kHz mono LINEAR16 WAV in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        num_samples = int(duration_sec * sample_rate)
        data = []
        for i in range(num_samples):
            # Sine wave
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
            data.append(struct.pack("<h", val))
        wf.writeframes(b"".join(data))
    return buf.getvalue()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------
# 1. API Health & Configuration Tests
# ---------------------------------------------------------

def test_health_endpoint(client):
    """GET /health must return 200 with service configuration and without leaking credentials."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "integrations" in data
    assert "gemini" in data["integrations"]
    assert "speech_to_text" in data["integrations"]
    assert "text_to_speech" in data["integrations"]
    # Verify supported languages are present
    assert "en-IN" in data["integrations"]["speech_to_text"]["supported_languages"]
    assert "hi-IN" in data["integrations"]["speech_to_text"]["supported_languages"]
    assert "kn-IN" in data["integrations"]["speech_to_text"]["supported_languages"]


def test_welcome_audio_endpoint(client):
    """GET /api/welcome-audio returns welcome message in the selected language."""
    for lang in ["en-IN", "hi-IN", "kn-IN"]:
        res = client.get(f"/api/welcome-audio?language_code={lang}")
        assert res.status_code == 200
        data = res.json()
        assert data["language_code"] == lang
        assert "welcome_text" in data
        assert len(data["welcome_text"]) > 10


def test_voice_turn_invalid_language(client):
    """POST /api/voice-turn with invalid language code must return 400."""
    wav_bytes = create_synthetic_wav(1.0)
    files = {"audio": ("test.wav", wav_bytes, "audio/wav")}
    data = {"language_code": "fr-FR"}
    res = client.post("/api/voice-turn", files=files, data=data)
    assert res.status_code == 400
    assert "not supported" in res.json()["detail"]


def test_chat_turn_invalid_language(client):
    """POST /api/chat-turn with invalid language code must return 400."""
    res = client.post("/api/chat-turn", json={"transcript": "hello", "language_code": "de-DE"})
    assert res.status_code == 400
    assert "not supported" in res.json()["detail"]


def test_voice_turn_empty_audio(client):
    """POST /api/voice-turn with empty file must return 400."""
    files = {"audio": ("test.wav", b"", "audio/wav")}
    res = client.post("/api/voice-turn", files=files, data={"language_code": "en-IN"})
    assert res.status_code == 400


# ---------------------------------------------------------
# 2. Audio Validation & Duration Limits
# ---------------------------------------------------------

def test_audio_validation():
    speech_svc = SpeechService()

    # Reject audio under 0.2s
    short_wav = create_synthetic_wav(0.1)
    is_valid, msg, _, _ = speech_svc.validate_audio(short_wav)
    assert not is_valid
    assert "too short" in msg

    # Accept standard 1s audio
    valid_wav = create_synthetic_wav(1.5)
    is_valid, msg, rate, channels = speech_svc.validate_audio(valid_wav)
    assert is_valid
    assert rate == 16000
    assert channels == 1


# ---------------------------------------------------------
# 3. Conversation History & Continuity (Mock Services)
# ---------------------------------------------------------

class MockSpeechService(SpeechService):
    def __init__(self, transcripts):
        self.transcripts = list(transcripts)
        self.idx = 0

    def transcribe(self, audio_bytes: bytes, language_code: str = "en-IN") -> str:
        if self.idx < len(self.transcripts):
            val = self.transcripts[self.idx]
            self.idx += 1
            return val
        return "Can you tell me more?"


class MockGeminiService(GeminiService):
    def __init__(self):
        self.call_history = []

    def generate_response(self, user_message: str, conversation_history: list, language_code: str = "en-IN") -> str:
        self.call_history.append({
            "message": user_message,
            "history_snapshot": list(conversation_history),
            "lang": language_code,
        })
        # Simulate conversational context retention
        lower_msg = user_message.lower()
        if "goa" in lower_msg:
            return "Goa is fantastic! How many days are you planning to stay?"
        elif "five days" in lower_msg:
            return "Got it. Five days in Goa. What is your budget for this trip?"
        elif "twenty-five thousand" in lower_msg or "25000" in lower_msg:
            return "Twenty-five thousand is a workable budget. Are you interested in beaches, sightseeing or adventure activities?"
        elif "water sports" in lower_msg:
            return "You can enjoy parasailing and jet skiing at Calangute and Baga beaches. Would you like a five-day itinerary featuring these?"
        elif "six days" in lower_msg:
            return "Updated to six days in Goa within twenty-five thousand rupees. Should we add South Goa heritage sites?"
        elif "गोवा" in user_message:
            return "गोवा बहुत सुंदर जगह है! आप कितने दिनों की यात्रा की योजना बना रहे हैं?"
        elif "ಗೋವಾ" in user_message:
            return "ಗೋವಾ ಅತ್ಯಂತ ಸುಂದರ ತಾಣ! ನೀವು ಎಷ್ಟು ದಿನಗಳ ಪ್ರವಾಸವನ್ನು ಯೋಜಿಸುತ್ತಿದ್ದೀರಿ?"
        return f"Understood. Let's plan that."


class MockTTSService(TTSService):
    def __init__(self):
        self._client = "mock_client"
        self._init_attempted = True

    @property
    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, language_code: str = "en-IN"):
        return b"MOCK_MP3_AUDIO_BYTES_" + text.encode("utf-8")[:20], "audio/mp3"


def test_conversation_continuity_5_turns():
    """
    Tests the mandatory Milestone 1 conversation sequence:
    1. "I want to visit Goa."
    2. "What can I do there for five days?"
    3. "My budget is twenty-five thousand."
    4. "What about water sports?"
    5. "Actually, make it six days."
    Verifies that session state and context are strictly retained across all turns.
    """
    script = [
        "I want to visit Goa.",
        "What can I do there for five days?",
        "My budget is twenty-five thousand.",
        "What about water sports?",
        "Actually, make it six days.",
    ]
    mock_stt = MockSpeechService(script)
    mock_gemini = MockGeminiService()
    mock_tts = MockTTSService()

    service = VoiceService(
        speech_service=mock_stt,
        gemini_service=mock_gemini,
        tts_service=mock_tts,
    )

    wav = create_synthetic_wav(1.0)
    conv_id = None

    for i, expected_query in enumerate(script):
        res = service.process_voice_turn(wav, conversation_id=conv_id, language_code="en-IN")
        conv_id = res["conversation_id"]
        assert res["transcript"] == expected_query
        assert res["response_text"]
        assert res["audio_base64"]
        assert res["action"] == "continue"

        # Check conversation history depth in Gemini service
        last_call = mock_gemini.call_history[-1]
        assert len(last_call["history_snapshot"]) == i * 2  # Each turn has user + assistant

    # Verify session retains all 10 messages (5 turns)
    session = service._sessions[conv_id]
    assert len(session["history"]) == 10
    # First turn is preserved
    assert session["history"][0]["content"] == "I want to visit Goa."
    # Last turn is preserved
    assert session["history"][-2]["content"] == "Actually, make it six days."


def test_hindi_conversation_turn():
    """Tests voice turn processing for Hindi (hi-IN)."""
    mock_stt = MockSpeechService(["मुझे गोवा जाना है।"])
    mock_gemini = MockGeminiService()
    mock_tts = MockTTSService()

    service = VoiceService(
        speech_service=mock_stt,
        gemini_service=mock_gemini,
        tts_service=mock_tts,
    )

    wav = create_synthetic_wav(1.0)
    res = service.process_voice_turn(wav, language_code="hi-IN")
    assert res["language_code"] == "hi-IN"
    assert res["transcript"] == "मुझे गोवा जाना है।"
    assert "गोवा" in res["response_text"]


def test_kannada_conversation_turn():
    """Tests voice turn processing for Kannada (kn-IN)."""
    mock_stt = MockSpeechService(["ನಾನು ಗೋವಾಕ್ಕೆ ಹೋಗಲು ಬಯಸುತ್ತೇನೆ."])
    mock_gemini = MockGeminiService()
    mock_tts = MockTTSService()

    service = VoiceService(
        speech_service=mock_stt,
        gemini_service=mock_gemini,
        tts_service=mock_tts,
    )

    wav = create_synthetic_wav(1.0)
    res = service.process_voice_turn(wav, language_code="kn-IN")
    assert res["language_code"] == "kn-IN"
    assert res["transcript"] == "ನಾನು ಗೋವಾಕ್ಕೆ ಹೋಗಲು ಬಯಸುತ್ತೇನೆ."
    assert "ಗೋವಾ" in res["response_text"]


def test_spoken_pause_command():
    """Tests spoken 'pause listening' command handling."""
    mock_stt = MockSpeechService(["pause listening"])
    mock_gemini = MockGeminiService()
    mock_tts = MockTTSService()

    service = VoiceService(
        speech_service=mock_stt,
        gemini_service=mock_gemini,
        tts_service=mock_tts,
    )

    wav = create_synthetic_wav(1.0)
    res = service.process_voice_turn(wav, language_code="en-IN")
    assert res["action"] == "pause"
    assert "paused" in res["response_text"].lower()


def test_spoken_language_switch():
    """Tests spoken language switch command."""
    mock_stt = MockSpeechService(["switch to Hindi"])
    mock_gemini = MockGeminiService()
    mock_tts = MockTTSService()

    service = VoiceService(
        speech_service=mock_stt,
        gemini_service=mock_gemini,
        tts_service=mock_tts,
    )

    wav = create_synthetic_wav(1.0)
    res = service.process_voice_turn(wav, language_code="en-IN")
    assert res["language_code"] == "hi-IN"
    assert "हिंदी" in res["response_text"]

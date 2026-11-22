"""
Text-to-Speech Service for Just Book It.
Integrates with Google Cloud Text-to-Speech API for Indian English, Hindi, and Kannada.
"""

import os
import io
import base64
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Supported voice configurations for Google Cloud Text-to-Speech
VOICE_CONFIGS: Dict[str, dict] = {
    "en-IN": {
        "language_code": "en-IN",
        "name": "en-IN-Neural2-A",  # High quality Neural2 voice
        "ssml_gender": "FEMALE",
        "speaking_rate": 1.0,
    },
    "hi-IN": {
        "language_code": "hi-IN",
        "name": "hi-IN-Neural2-A",  # High quality Neural2 voice
        "ssml_gender": "FEMALE",
        "speaking_rate": 1.0,
    },
    "kn-IN": {
        "language_code": "kn-IN",
        "name": "kn-IN-Standard-A",  # Officially supported Kannada standard voice
        "ssml_gender": "FEMALE",
        "speaking_rate": 1.0,
    },
}

WELCOME_MESSAGES: Dict[str, str] = {
    "en-IN": (
        "Welcome to Just Book It, your hands-free travel assistant. "
        "You can speak naturally to plan your trip. "
        "We support English, Hindi, and Kannada. Say your preferred language to begin."
    ),
    "hi-IN": (
        "जस्ट बुक इट में आपका स्वागत है, यह आपका हैंड्स-फ्री यात्रा सहायक है। "
        "आप अपनी यात्रा की योजना बनाने के लिए स्वाभाविक रूप से बात कर सकते हैं। "
        "आरंभ करने के लिए अपनी पसंदीदा भाषा बोलें।"
    ),
    "kn-IN": (
        "ಜಸ್ಟ್ ಬುಕ್ ಇಟ್‌ಗೆ ಸ್ವಾಗತ, ಇದು ನಿಮ್ಮ ಹ್ಯಾಂಡ್ಸ್-ಫ್ರೀ ಪ್ರವಾಸ ಸಹಾಯಕ. "
        "ನಿಮ್ಮ ಪ್ರವಾಸವನ್ನು ಯೋಜಿಸಲು ನೀವು ಸಹಜವಾಗಿ ಮಾತನಾಡಬಹುದು. "
        "ಪ್ರಾರಂಭಿಸಲು ನಿಮ್ಮ ನೆಚ್ಚಿನ ಭಾಷೆಯನ್ನು ತಿಳಿಸಿ."
    ),
}


class TTSService:
    def __init__(self):
        self._client = None
        self._init_attempted = False
        self._last_creds_env = None
        self._init_client()

    def _init_client(self):
        """Initializes Google Cloud Text-to-Speech client."""
        current_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not current_creds or not os.path.exists(current_creds):
            # No valid credentials file on disk - skip GCP init without warning
            logger.info("Google Cloud credentials not configured. Text-to-Speech will operate via browser Web Speech API.")
            self._client = None
            self._init_attempted = True
            return

        if self._init_attempted and current_creds == self._last_creds_env and not self._client:
            return

        self._init_attempted = True
        self._last_creds_env = current_creds

        try:
            from google.cloud import texttospeech_v1 as texttospeech
            self._client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud Text-to-Speech client initialized successfully.")
        except Exception as e:
            logger.warning(f"Google Cloud Text-to-Speech client initialization error: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def synthesize(self, text: str, language_code: str = "en-IN") -> Tuple[bytes, str]:
        """
        Converts text to spoken MP3 audio using Google Cloud Text-to-Speech.
        
        Args:
            text: Plain text to synthesize.
            language_code: Target language code ('en-IN', 'hi-IN', 'kn-IN').
            
        Returns:
            Tuple of (audio_bytes, mime_type)
        """
        if not text or not text.strip():
            raise ValueError("Text to synthesize cannot be empty.")

        if language_code not in VOICE_CONFIGS:
            language_code = "en-IN"

        if not self._client:
            self._init_client()
            if not self._client:
                raise RuntimeError(
                    "Google Cloud Text-to-Speech client is not initialized. "
                    "Please set GOOGLE_APPLICATION_CREDENTIALS in your environment."
                )

        from google.cloud import texttospeech_v1 as texttospeech

        voice_info = VOICE_CONFIGS[language_code]
        synthesis_input = texttospeech.SynthesisInput(text=text)

        gender_enum = (
            texttospeech.SsmlVoiceGender.FEMALE
            if voice_info["ssml_gender"] == "FEMALE"
            else texttospeech.SsmlVoiceGender.MALE
        )

        voice = texttospeech.VoiceSelectionParams(
            language_code=voice_info["language_code"],
            name=voice_info["name"],
            ssml_gender=gender_enum,
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=voice_info.get("speaking_rate", 1.0),
        )

        try:
            response = self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            logger.info(f"Synthesized {len(response.audio_content)} bytes of speech audio ({language_code}).")
            return response.audio_content, "audio/mp3"
        except Exception as e:
            logger.error(f"Google Cloud TTS synthesis failed: {e}")
            raise RuntimeError(f"Text-to-Speech API error: {str(e)}")

    def get_welcome_audio(self, language_code: str = "en-IN") -> Tuple[str, bytes, str]:
        """
        Returns (welcome_text, audio_bytes, mime_type) for initial launch.
        """
        text = WELCOME_MESSAGES.get(language_code, WELCOME_MESSAGES["en-IN"])
        audio_bytes, mime_type = self.synthesize(text, language_code)
        return text, audio_bytes, mime_type

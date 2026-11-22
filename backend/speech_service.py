"""
Speech-to-Text Service for Just Book It.
Integrates with Google Cloud Speech-to-Text API for Indian English, Hindi, and Kannada.
"""

import os
import io
import wave
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en-IN": "English (India)",
    "hi-IN": "Hindi (India)",
    "kn-IN": "Kannada (India)",
}


class SpeechService:
    def __init__(self):
        self._client = None
        self._init_attempted = False
        self._last_creds_env = None
        self._init_client()

    def _init_client(self):
        """Initializes Google Cloud Speech client if credentials are configured."""
        current_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not current_creds or not os.path.exists(current_creds):
            # No valid credentials file on disk - skip GCP init without warning
            logger.info("Google Cloud credentials not configured. Speech-to-Text will operate via browser Web Speech API.")
            self._client = None
            self._init_attempted = True
            return

        if self._init_attempted and current_creds == self._last_creds_env and not self._client:
            return

        self._init_attempted = True
        self._last_creds_env = current_creds

        try:
            from google.cloud import speech_v1 as speech
            self._client = speech.SpeechClient()
            logger.info("Google Cloud Speech client initialized successfully.")
        except Exception as e:
            logger.warning(f"Google Cloud Speech client initialization error: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        """Returns True if Google Cloud Speech client is initialized."""
        return self._client is not None

    def validate_audio(self, audio_bytes: bytes) -> tuple[bool, str, int, int]:
        """
        Validates WAV audio bytes:
        - Checks minimum and maximum size
        - Inspects WAV header for sample rate and channels
        Returns (is_valid, message, sample_rate, num_channels)
        """
        if not audio_bytes or len(audio_bytes) < 44:
            return False, "Audio file is empty or too short to contain a valid WAV header.", 0, 0

        # Maximum size: 15MB (~8 minutes of 16kHz mono 16-bit PCM)
        if len(audio_bytes) > 15 * 1024 * 1024:
            return False, "Audio file exceeds maximum allowed size of 15MB.", 0, 0

        try:
            with io.BytesIO(audio_bytes) as bio:
                with wave.open(bio, "rb") as wf:
                    channels = wf.getnchannels()
                    sample_rate = wf.getframerate()
                    sample_width = wf.getsampwidth()
                    num_frames = wf.getnframes()
                    duration_sec = num_frames / float(sample_rate) if sample_rate > 0 else 0

                    if duration_sec < 0.2:
                        return False, f"Utterance too short ({duration_sec:.2f}s).", sample_rate, channels
                    if duration_sec > 65.0:
                        return False, f"Utterance exceeds maximum limit of 60 seconds ({duration_sec:.2f}s).", sample_rate, channels

                    return True, "Valid WAV audio.", sample_rate, channels
        except wave.Error as e:
            # Not a strict WAV header or raw PCM; allow STT if bytes exist
            return True, f"Audio raw stream check passed ({len(audio_bytes)} bytes): {e}", 16000, 1

    def transcribe(self, audio_bytes: bytes, language_code: str = "en-IN") -> str:
        """
        Transcribes audio bytes to text using Google Cloud Speech-to-Text.
        
        Args:
            audio_bytes: Raw 16kHz LINEAR16 WAV audio data.
            language_code: BCP-47 language tag ('en-IN', 'hi-IN', 'kn-IN').
            
        Returns:
            The recognized transcript text.
        """
        if language_code not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language code '{language_code}'. "
                f"Supported languages: {list(SUPPORTED_LANGUAGES.keys())}"
            )

        if not self._client:
            self._init_client()
            if not self._client:
                raise RuntimeError(
                    "Google Cloud Speech client is not initialized. "
                    "Please set GOOGLE_APPLICATION_CREDENTIALS in your environment."
                )

        from google.cloud import speech_v1 as speech

        is_valid, msg, sample_rate, channels = self.validate_audio(audio_bytes)
        if not is_valid:
            raise ValueError(f"Audio validation failed: {msg}")

        # Configure Google Cloud Speech recognition
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate if sample_rate in (8000, 16000, 24000, 44100, 48000) else 16000,
            language_code=language_code,
            enable_automatic_punctuation=True,
            audio_channel_count=channels if channels > 1 else 1,
            model="default",
        )

        audio = speech.RecognitionAudio(content=audio_bytes)

        try:
            response = self._client.recognize(config=config, audio=audio)
            transcripts = []
            for result in response.results:
                if result.alternatives:
                    transcripts.append(result.alternatives[0].transcript)

            final_text = " ".join(transcripts).strip()
            logger.info(f"Speech transcription ({language_code}): '{final_text}'")
            return final_text
        except Exception as e:
            logger.error(f"Google Cloud Speech recognition failed: {e}")
            raise RuntimeError(f"Speech-to-Text API error: {str(e)}")

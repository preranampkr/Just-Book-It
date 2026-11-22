"""
Gemini Service for Just Book It.
Uses the official google-genai Python SDK to power the conversational travel assistant.
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are "Just Book It", an empathetic, completely hands-free voice AI travel-planning assistant.
You are conversing with users entirely through spoken audio (No Screens theme). Blind users, elderly people, and users who cannot use their hands rely on you.

Crucial Voice Communication Rules:
1. Speak in natural, warm, conversational sentences that sound fluent when read aloud by Text-to-Speech.
2. KEEP RESPONSES CONCISE (typically 1 to 3 short sentences). Avoid long paragraphs, overwhelming lists, or monologues.
3. NEVER output markdown symbols (no asterisks, hashes, bullet points, numbers lists, bolding, italics, or tables). Write plain spoken prose only.
4. Always respond in the exact requested language:
   - For English (en-IN): Natural Indian English.
   - For Hindi (hi-IN): Fluent, conversational Hindi (in Devanagari script).
   - For Kannada (kn-IN): Fluent, conversational Kannada (in Kannada script).

Travel Interaction Stages:
1. Exploration: Help the user explore destinations, attractions, and activities naturally.
2. Planning: Ask clarifying questions about duration, budget, companions, and preferences. Retain context across turns (e.g. if the user says "What about water sports?", remember they are still discussing Goa).
3. Execution: For this prototype, bookings and financial transactions are NOT connected. If a user asks to book or asks for exact live ticket/hotel prices, politely explain that live booking and real-time supplier pricing are not connected yet, but you can help them plan every detail.
4. NEVER claim that a booking or reservation has been made.
5. NEVER invent live flight or hotel rates.
"""

LANGUAGE_INSTRUCTIONS = {
    "en-IN": "Respond in warm, clear, conversational Indian English.",
    "hi-IN": "कृपया स्वाभाविक और बातचीत की हिंदी में उत्तर दें (देवनागरी लिपि में)।",
    "kn-IN": "ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟ ಮತ್ತು ಆಪ್ತವಾದ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ (ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ).",
}


class GeminiService:
    def __init__(self):
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initializes the official google-genai client."""
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY", "")
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized with model '{self.model_name}'.")
            except Exception as e:
                logger.error(f"Failed to initialize google-genai client: {e}")
                self._client = None
        else:
            logger.warning("GEMINI_API_KEY not set. Gemini integration is uninitialized.")
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        language_code: str = "en-IN",
    ) -> str:
        """
        Generates a travel-assistant response using the official google-genai SDK.
        
        Args:
            user_message: The transcribed user text.
            conversation_history: List of past messages [{'role': 'user'|'assistant', 'content': '...'}]
            language_code: Target language ('en-IN', 'hi-IN', 'kn-IN').
            
        Returns:
            Clean conversational spoken response text.
        """
        if not self._client:
            self._init_client()
            if not self._client:
                raise RuntimeError(
                    "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env"
                )

        from google.genai import types

        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language_code, LANGUAGE_INSTRUCTIONS["en-IN"])
        full_system_instruction = f"{SYSTEM_PROMPT}\n\nCurrent language requirement: {lang_instruction}"

        # Build contents from conversation history
        # google-genai expects contents as list of Content or dicts
        contents = []
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        # Append current user message
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)]
            )
        )

        try:
            config = types.GenerateContentConfig(
                system_instruction=full_system_instruction,
                temperature=0.7,
                max_output_tokens=300,
            )
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

            response_text = response.text.strip() if response.text else ""
            # Strip any residual markdown characters (e.g. *, #, _) that could sound weird when read aloud
            clean_text = (
                response_text.replace("*", "")
                .replace("#", "")
                .replace("`", "")
                .replace("~", "")
                .replace("\n\n", " ")
                .replace("\n", " ")
                .strip()
            )
            logger.info(f"Gemini response generated ({language_code}): '{clean_text}'")
            return clean_text
        except Exception as e:
            logger.error(f"Gemini generate_content failed: {e}")
            raise RuntimeError(f"Gemini API error: {str(e)}")

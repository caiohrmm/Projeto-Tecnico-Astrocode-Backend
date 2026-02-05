"""Gemini API client service for AI chat."""

import logging
import os
from typing import Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API."""

    MODEL_NAME = "gemini-2.5-flash"  # Using 2.0-flash-exp (2.5-flash not available yet)
    TIMEOUT_SECONDS = 30

    def __init__(self) -> None:
        """Initialize Gemini service with API key from settings."""
        settings = get_settings()
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        
        if not api_key:
            logger.warning("GEMINI_API_KEY not configured. Chat functionality will be limited.")
            self.api_key = None
        else:
            # Clean API key (remove quotes, whitespace, etc.)
            api_key = api_key.strip().strip('"').strip("'").lstrip('-').replace('\n', '').replace('\r', '').replace(' ', '')
            self.api_key = api_key
            genai.configure(api_key=self.api_key)

    def is_configured(self) -> bool:
        """Check if Gemini API is properly configured."""
        return self.api_key is not None and len(self.api_key) > 0

    def chat(
        self,
        message: str,
        system_prompt: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a chat message to Gemini API.
        
        Args:
            message: User's message/question
            system_prompt: System prompt with instructions
            context: Optional context data from database
        
        Returns:
            Dictionary with 'answer' and 'error' keys
        
        Raises:
            Exception: If API call fails
        """
        if not self.is_configured():
            return {
                "answer": "AI chat is not configured. Please set GEMINI_API_KEY in environment variables.",
                "error": "API key not configured",
            }

        try:
            # Build full prompt with context
            full_prompt = system_prompt
            if context:
                full_prompt += f"\n\n=== CONTEXT DATA ===\n{context}\n\n=== END CONTEXT ===\n\n"
            full_prompt += f"\nUser question: {message}\n\nAnswer:"

            # Configure safety settings (allow all content for CRM use)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            # Generate content
            model = genai.GenerativeModel(
                model_name=self.MODEL_NAME,
                safety_settings=safety_settings,
            )

            response = model.generate_content(
                full_prompt,
                request_options={"timeout": self.TIMEOUT_SECONDS},
            )

            answer = response.text.strip() if response.text else "No response from AI."

            return {
                "answer": answer,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}", exc_info=True)
            return {
                "answer": f"Error communicating with AI service: {str(e)}",
                "error": str(e),
            }


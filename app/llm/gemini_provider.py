from typing import Iterator
from google import genai
from app.core.config import get_settings
from app.llm.provider import BaseLLMProvider, LLMError
import logging

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key, vertexai=False)
        self.model = settings.llm_model

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            return response.text
        except Exception as exc:
            logger.exception("Gemini generation failed")
            raise LLMError(str(exc)) from exc

    def stream(self, prompt: str) -> Iterator[str]:
        try:
            for chunk in self.client.models.generate_content_stream(model=self.model, contents=prompt):
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.exception("Gemini streaming failed")
            raise LLMError(str(exc)) from exc
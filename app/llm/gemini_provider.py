import logging
from google import genai
from app.core.config import get_settings
from app.llm.provider import BaseLLMProvider, LLMError

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.llm_model

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            return response.text
        except Exception as exc:
            logger.exception("Gemini generation failed")
            raise LLMError(str(exc)) from exc

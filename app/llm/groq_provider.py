from typing import Iterator
from groq import Groq
from app.core.config import get_settings
from app.llm.provider import BaseLLMProvider, LLMError
import logging

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.exception("Groq generation failed")
            raise LLMError(str(exc)) from exc

    def stream(self, prompt: str) -> Iterator[str]:
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            logger.exception("Groq streaming failed")
            raise LLMError(str(exc)) from exc
from abc import ABC, abstractmethod


class LLMError(Exception):
    """Raised when LLM generation fails."""


class BaseLLMProvider(ABC):
    """
    Interface every LLM provider must implement. The RAG pipeline only ever
    talks to this interface — it never knows or cares whether it's Gemini,
    Groq, or anything else behind it.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function — reads LLM_PROVIDER from settings and returns the
    matching provider instance. This is the single place that decides which
    concrete provider gets used; everything else just calls get_llm_provider().
    """
    from app.core.config import get_settings
    settings = get_settings()

    if settings.llm_provider == "groq":
        from app.llm.groq_provider import GroqProvider
        return GroqProvider()

    from app.llm.gemini_provider import GeminiProvider
    return GeminiProvider()
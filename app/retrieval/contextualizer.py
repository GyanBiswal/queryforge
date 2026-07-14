import logging
from app.llm.provider import get_llm_provider, LLMError

logger = logging.getLogger(__name__)

CONTEXTUALIZE_PROMPT_TEMPLATE = """Given the conversation history and a follow-up \
question, rewrite the follow-up into a standalone question that can be understood \
without the history. If the follow-up is already standalone, return it unchanged. \
Do not answer the question — only rewrite it. Output ONLY the rewritten question, \
nothing else.

Conversation history:
{history}

Follow-up question: {question}

Standalone question:"""


def contextualize_question(question: str, history: list[dict]) -> str:
    """
    Rewrites a follow-up question into a standalone one using recent turns.
    Falls back to the original question if history is empty or rewriting fails —
    fails safe rather than blocking the whole query on a non-critical step.
    """
    if not history:
        return question

    history_text = "\n".join(
        f"User: {turn['question']}\nAssistant: {turn['answer']}" for turn in history
    )
    prompt = CONTEXTUALIZE_PROMPT_TEMPLATE.format(history=history_text, question=question)

    try:
        llm = get_llm_provider()
        rewritten = llm.generate(prompt).strip()
        logger.info("Contextualized '%s' -> '%s'", question, rewritten)
        return rewritten
    except LLMError:
        logger.exception("Contextualization failed, falling back to original question")
        return question
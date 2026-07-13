import re


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks, preferring sentence boundaries.

    Blind character-count splitting cuts sentences (and sometimes words) in
    half, which hurts retrieval quality — a chunk ending mid-sentence loses
    context the embedding model would otherwise capture. Instead we split
    into sentences first, then greedily pack them into ~chunk_size windows.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > chunk_size and current:
            chunks.append(" ".join(current))
            # carry the tail of the previous chunk forward for overlap
            current, current_len = _take_overlap(current, overlap)

        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def _split_sentences(text: str) -> list[str]:
    # Simple regex split on sentence-ending punctuation followed by whitespace.
    # Not perfect (abbreviations like "Mr." will split early) — acceptable
    # for v1; spaCy/nltk sentence tokenizers are the documented upgrade path.
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _take_overlap(sentences: list[str], overlap: int) -> tuple[list[str], int]:
    """Keep trailing sentences from the previous chunk up to `overlap` chars."""
    kept: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        if total + len(sentence) > overlap:
            break
        kept.insert(0, sentence)
        total += len(sentence)
    return kept, total
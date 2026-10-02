import re
from typing import Optional
from app.ai.providers.factory import get_llm_provider

DOC_TYPES = [
    "meeting_note",
    "paper",
    "experiment_log",
    "design_doc",
    "dataset_card",
    "other",
]

def classify_doc_heuristics(filename: str, snippet: str) -> Optional[str]:
    """Fast deterministic heuristics for document classification."""
    fn = filename.lower()
    snip = snippet.lower()

    if fn.endswith(".csv") or "experiment" in fn or re.search(r"exp[-_]\d+", fn) or "benchmark" in snip[:200]:
        return "experiment_log"
    if "meeting" in fn or "sync" in fn or re.search(r"m[-_]\d+", fn) or "attendees:" in snip[:200]:
        return "meeting_note"
    if "paper" in fn or re.search(r"r[-_]\d+", fn) or "arxiv" in snip[:200] or "abstract" in snip[:200]:
        return "paper"
    if "doc" in fn or "architecture" in fn or "design" in fn or "specification" in snip[:200]:
        return "design_doc"
    if "dataset" in fn or "dataset_card" in fn:
        return "dataset_card"

    return None

async def classify_document_type(
    filename: str,
    full_text: str,
    user_override: Optional[str] = None,
) -> str:
    """Classifies document type using heuristics or Haiku-class LLM."""
    if user_override and user_override in DOC_TYPES:
        return user_override

    # Try heuristic first
    heuristic = classify_doc_heuristics(filename, full_text[:500])
    if heuristic:
        return heuristic

    # Fallback to LLM
    try:
        llm = get_llm_provider()
        prompt = (
            f"Classify the following document into exactly ONE category from: {', '.join(DOC_TYPES)}.\n\n"
            f"Filename: {filename}\n"
            f"Content snippet:\n{full_text[:1000]}\n\n"
            f"Respond ONLY with the category name (e.g. meeting_note)."
        )
        response = await llm.complete(prompt, temperature=0.0)
        category = response.strip().lower()
        for dt in DOC_TYPES:
            if dt in category:
                return dt
    except Exception:
        pass

    return "other"

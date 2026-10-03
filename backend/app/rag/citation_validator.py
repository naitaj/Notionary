import re
from typing import List, Dict, Tuple, Optional
from app.schemas.contracts import Citation

REFUSAL_TEXT = "I couldn't find sufficient project evidence to answer this reliably."

def extract_citation_numbers(text: str) -> List[int]:
    """Extracts all [n] integer citation references from text."""
    matches = re.findall(r"\[(\d+)\]", text)
    numbers = []
    for m in matches:
        try:
            numbers.append(int(m))
        except ValueError:
            continue
    return numbers

def validate_citations_and_refusal(
    answer_text: str,
    citation_map: Dict[int, Citation],
    require_citations: bool = True,
) -> Tuple[bool, List[Citation], Optional[str]]:
    """
    Plan §4.6: Citation validator.
    Ensures every [n] cited in the answer strictly resolves to an item in citation_map.
    Returns:
    - is_valid: bool (True if all citations are valid and sufficient)
    - active_citations: list of Citation objects referenced by the answer
    - failure_reason: Optional explanation if validation failed
    """
    if not answer_text or not answer_text.strip():
        return False, [], "Empty answer received."

    # Check if the LLM explicitly expressed refusal
    if REFUSAL_TEXT.lower() in answer_text.lower() or "cannot find sufficient" in answer_text.lower():
        return True, [], None

    citation_nums = extract_citation_numbers(answer_text)

    # Check if context is completely empty
    if not citation_map:
        return False, [], "No project context was supplied."

    # Check for ungrounded answer (requires citations for factual queries)
    if require_citations and not citation_nums:
        return False, [], "Answer lacks required citations to supplied evidence."

    # Verify each cited number exists in citation_map
    invalid_nums = [n for n in citation_nums if n not in citation_map]
    if invalid_nums:
        return False, [], f"Answer cited non-existent context indices: {invalid_nums}"

    # Collect unique active citations in order of appearance
    seen = set()
    active_citations: List[Citation] = []
    for n in citation_nums:
        if n not in seen and n in citation_map:
            seen.add(n)
            active_citations.append(citation_map[n])

    return True, active_citations, None

from typing import List, Dict, Tuple
from app.rag.retrieval import RetrievedContextItem
from app.schemas.contracts import Citation

def assemble_rag_context(
    items: List[RetrievedContextItem],
) -> Tuple[str, Dict[int, Citation], Dict[str, int]]:
    """
    Plan §4.5: Context assembly.
    Formats retrieved records + excerpts + provenance labels with stable numbering [1], [2], ...
    Returns:
    - context_str: numbered text block formatted for LLM prompt
    - citation_map: mapping of citation index -> Citation object
    - provenance_counts: count of items by provenance origin
    """
    context_blocks: List[str] = []
    citation_map: Dict[int, Citation] = {}
    provenance_counts: Dict[str, int] = {
        "human_authored": 0,
        "system_derived": 0,
        "ai_inferred": 0,
    }

    seen_texts = set()
    citation_idx = 1

    for item in items:
        # Avoid duplicate blocks
        norm_text = item.text_content.strip()
        if not norm_text or norm_text in seen_texts:
            continue
        seen_texts.add(norm_text)

        origin = item.origin if item.origin in provenance_counts else "human_authored"
        provenance_counts[origin] = provenance_counts.get(origin, 0) + 1

        date_str = f" | Date: {item.source_date}" if item.source_date else ""
        header = f"[{citation_idx}] Source: {item.code_or_title} | Provenance: {origin}{date_str}"
        block = f"{header}\n{norm_text}"
        context_blocks.append(block)

        # Build citation mapping
        citation = Citation(
            citation_number=citation_idx,
            entity_type=item.entity_type,
            entity_id=item.id,
            code_or_title=item.code_or_title,
            excerpt=norm_text[:280] + ("..." if len(norm_text) > 280 else ""),
            origin=origin,
            source_date=item.source_date,
            notion_url=item.notion_url,
        )
        citation_map[citation_idx] = citation
        citation_idx += 1

    context_str = "\n\n".join(context_blocks)
    return context_str, citation_map, provenance_counts

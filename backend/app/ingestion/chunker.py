from typing import List, Dict, Any

MAX_CHUNK_CHARS = 1600  # ~350-400 tokens
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200     # ~15% overlap

def create_structure_aware_chunks(
    full_text: str,
    blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Creates structure-aware chunks respecting heading boundaries and preserving exact character offsets
    such that full_text[chunk['char_start']:chunk['char_end']] == chunk['text'].
    """
    chunks = []

    for block in blocks:
        block_text = block["text"]
        b_start = block["char_start"]
        b_end = block["char_end"]
        heading_path = block.get("heading_path", "General")

        # Sanity check: Ensure block bounds align with full_text
        if full_text[b_start:b_end] != block_text:
            # Fallback alignment if whitespace differences occurred
            b_start = full_text.find(block_text)
            if b_start != -1:
                b_end = b_start + len(block_text)
            else:
                continue

        # If block fits in one chunk, keep it intact
        if len(block_text) <= MAX_CHUNK_CHARS:
            if len(block_text.strip()) > 0:
                chunks.append({
                    "text": block_text,
                    "heading_path": heading_path,
                    "char_start": b_start,
                    "char_end": b_end,
                })
            continue

        # For larger blocks, break into overlapping sub-chunks at sentence or line boundaries
        offset = 0
        while offset < len(block_text):
            chunk_len = min(MAX_CHUNK_CHARS, len(block_text) - offset)
            sub_text = block_text[offset : offset + chunk_len]

            # If not at the end of the block, look for clean break (newline or period)
            if offset + chunk_len < len(block_text):
                break_point = max(sub_text.rfind("\n"), sub_text.rfind(". "))
                if break_point > MIN_CHUNK_CHARS:
                    sub_text = sub_text[: break_point + 1]
                    chunk_len = len(sub_text)

            c_start = b_start + offset
            c_end = c_start + len(sub_text)

            # Strict invariant check
            chunk_slice = full_text[c_start:c_end]
            if chunk_slice:
                chunks.append({
                    "text": chunk_slice,
                    "heading_path": heading_path,
                    "char_start": c_start,
                    "char_end": c_end,
                })

            step = max(1, chunk_len - OVERLAP_CHARS)
            offset += step

    return chunks

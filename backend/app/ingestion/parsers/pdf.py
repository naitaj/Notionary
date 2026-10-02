from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF

def parse_pdf(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses PDF using PyMuPDF page-by-page, accumulating text and tracking character offsets.
    """
    doc = fitz.open(file_path)
    full_text_parts = []
    blocks = []
    current_char_offset = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text").strip()
        if not page_text:
            continue

        char_start = current_char_offset
        char_end = char_start + len(page_text)
        blocks.append({
            "text": page_text,
            "heading_path": f"Page {page_num + 1}",
            "char_start": char_start,
            "char_end": char_end,
        })
        full_text_parts.append(page_text)
        current_char_offset = char_end + 2  # account for "\n\n" between pages

    doc.close()
    full_text = "\n\n".join(full_text_parts)
    return full_text, blocks

from typing import List, Dict, Any, Tuple
import docx

def parse_docx(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses DOCX document into paragraphs with heading hierarchy and offsets.
    """
    doc = docx.Document(file_path)
    full_text_parts = []
    blocks = []
    current_offset = 0
    current_heading = "Document"

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if para.style.name.startswith("Heading"):
            current_heading = text

        char_start = current_offset
        char_end = char_start + len(text)
        blocks.append({
            "text": text,
            "heading_path": current_heading,
            "char_start": char_start,
            "char_end": char_end,
        })
        full_text_parts.append(text)
        current_offset = char_end + 1  # newline

    full_text = "\n".join(full_text_parts)
    return full_text, blocks

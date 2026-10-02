from typing import List, Dict, Any, Tuple

def parse_plain_text(content_str: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses plain text document into blocks while strictly preserving character offsets
    such that content_str[char_start:char_end] == block['text'].
    """
    content_str = content_str.replace("\r\n", "\n")
    blocks = []
    lines = content_str.split("\n")
    current_offset = 0
    current_heading = "General"

    current_block_lines = []
    block_start = 0

    for line in lines:
        line_len = len(line) + 1  # include newline
        stripped = line.strip()

        # Check if line looks like a section header (e.g. # Title, Meeting:, Date:)
        if stripped.startswith("#") or (stripped.endswith(":") and len(stripped) < 60):
            # Flush existing block if present
            if current_block_lines:
                block_text = "\n".join(current_block_lines)
                blocks.append({
                    "text": block_text,
                    "heading_path": current_heading,
                    "char_start": block_start,
                    "char_end": block_start + len(block_text),
                })
                current_block_lines = []

            current_heading = stripped.lstrip("#").strip()
            block_start = current_offset
            current_block_lines.append(line)
        else:
            if not current_block_lines:
                block_start = current_offset
            current_block_lines.append(line)

        current_offset += line_len

    if current_block_lines:
        block_text = "\n".join(current_block_lines)
        blocks.append({
            "text": block_text,
            "heading_path": current_heading,
            "char_start": block_start,
            "char_end": block_start + len(block_text),
        })

    # If no blocks were created (empty file)
    if not blocks and content_str:
        blocks.append({
            "text": content_str,
            "heading_path": "General",
            "char_start": 0,
            "char_end": len(content_str),
        })

    return content_str, blocks

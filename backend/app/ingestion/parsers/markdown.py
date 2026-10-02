import re
from typing import List, Dict, Any, Tuple

def parse_markdown(content_str: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parses Markdown into hierarchical blocks with heading paths,
    ensuring content_str[char_start:char_end] == block['text'].
    """
    content_str = content_str.replace("\r\n", "\n")
    blocks = []
    lines = content_str.split("\n")
    current_offset = 0
    heading_stack: List[Tuple[int, str]] = []  # (level, title)

    current_block_lines: List[str] = []
    block_start = 0

    def current_heading_path() -> str:
        if not heading_stack:
            return "Root"
        return " > ".join(title for _, title in heading_stack)

    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

    for line in lines:
        line_len = len(line) + 1
        match = heading_pattern.match(line)

        if match:
            # Flush previous block
            if current_block_lines:
                block_text = "\n".join(current_block_lines)
                blocks.append({
                    "text": block_text,
                    "heading_path": current_heading_path(),
                    "char_start": block_start,
                    "char_end": block_start + len(block_text),
                })
                current_block_lines = []

            level = len(match.group(1))
            title = match.group(2).strip()

            # Adjust heading stack hierarchy
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

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
            "heading_path": current_heading_path(),
            "char_start": block_start,
            "char_end": block_start + len(block_text),
        })

    return content_str, blocks

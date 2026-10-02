import os
from typing import Tuple, List, Dict, Any
from app.ingestion.parsers.text import parse_plain_text
from app.ingestion.parsers.markdown import parse_markdown
from app.ingestion.parsers.pdf import parse_pdf
from app.ingestion.parsers.docx import parse_docx
from app.ingestion.parsers.csv_parser import parse_csv_file

def parse_file(file_path: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Dispatcher parsing a document into (full_text, blocks, metadata)
    where full_text[char_start:char_end] matches block['text'].
    """
    _, ext = os.path.splitext(file_path.lower())
    metadata: Dict[str, Any] = {"extension": ext, "file_path": file_path}

    if ext in (".md", ".markdown"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_text, blocks = parse_markdown(content)
        return full_text, blocks, metadata

    elif ext == ".pdf":
        full_text, blocks = parse_pdf(file_path)
        return full_text, blocks, metadata

    elif ext == ".docx":
        full_text, blocks = parse_docx(file_path)
        return full_text, blocks, metadata

    elif ext == ".csv":
        full_text, blocks, df = parse_csv_file(file_path)
        metadata["dataframe"] = df
        return full_text, blocks, metadata

    else:
        # Default to plain text
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_text, blocks = parse_plain_text(content)
        return full_text, blocks, metadata

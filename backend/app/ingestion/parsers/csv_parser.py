import pandas as pd
from typing import List, Dict, Any, Tuple

def parse_csv_file(file_path: str) -> Tuple[str, List[Dict[str, Any]], pd.DataFrame]:
    """
    Parses CSV file using pandas, generating tabular text blocks with character offsets.
    """
    df = pd.read_csv(file_path)
    full_text_lines = []
    blocks = []
    current_offset = 0

    # Header line
    headers = list(df.columns)
    header_str = " | ".join(str(h) for h in headers)
    full_text_lines.append(header_str)
    current_offset += len(header_str) + 1

    for idx, row in df.iterrows():
        row_parts = [f"{col}: {row[col]}" for col in headers if pd.notna(row[col])]
        row_str = "Row " + str(idx + 1) + " -> " + ", ".join(row_parts)
        
        char_start = current_offset
        char_end = char_start + len(row_str)
        blocks.append({
            "text": row_str,
            "heading_path": f"Row {idx + 1}",
            "char_start": char_start,
            "char_end": char_end,
            "row_dict": row.to_dict(),
        })
        full_text_lines.append(row_str)
        current_offset = char_end + 1

    full_text = "\n".join(full_text_lines)
    return full_text, blocks, df

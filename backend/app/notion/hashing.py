import hashlib
import json
from typing import Dict, Any, List

HUMAN_OWNED_FIELDS = {
    "decisions": ["statement", "rationale", "status", "decided_by"],
    "tasks": ["title", "status", "priority", "owner", "due_date"],
    "claims": ["statement", "subject", "metric", "direction", "dataset", "value"],
    "experiments": ["hypothesis", "model", "dataset", "status", "owner"],
    "deliverables": ["name", "status", "due_date"],
    "milestones": ["name", "due_date"],
}

def extract_plain_text(prop: Dict[str, Any]) -> str:
    """Extracts raw string text from rich_text or title Notion property objects."""
    if not isinstance(prop, dict):
        return str(prop or "").strip()

    items = prop.get("rich_text") or prop.get("title")
    if items is not None and isinstance(items, list):
        parts = []
        for item in items:
            if isinstance(item, dict):
                parts.append(item.get("plain_text") or item.get("text", {}).get("content", ""))
            else:
                parts.append(str(item))
        return "".join(parts).strip()

    if "select" in prop:
        sel = prop.get("select")
        return sel.get("name", "").strip() if sel else ""
    if "number" in prop:
        num = prop.get("number")
        return str(num) if num is not None else ""
    if "date" in prop:
        d = prop.get("date")
        return d.get("start", "") if d else ""
    if "checkbox" in prop:
        return str(prop.get("checkbox", False))
    return ""
    return ""

def compute_human_hash(entity_type: str, data: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 hash across human-owned properties.
    Ignores machine-managed fields (POS_ID, sync timestamps, origin, relations).
    """
    fields = HUMAN_OWNED_FIELDS.get(entity_type.lower(), list(data.keys()))
    normalized_pairs = []
    
    for f in sorted(fields):
        val = data.get(f)
        if isinstance(val, dict) and "type" in val:
            # Notion property object
            text_val = extract_plain_text(val)
        elif val is not None:
            text_val = str(val).strip()
        else:
            text_val = ""
        normalized_pairs.append(f"{f}:{text_val}")

    raw_string = "|".join(normalized_pairs)
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

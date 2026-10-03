import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class QueryIntent(BaseModel):
    raw_query: str
    intent_type: str  # decision, experiment, task, contradiction, general
    entity_codes: List[str] = []
    keywords: List[str] = []
    model_aliases: List[str] = []
    people_mentions: List[str] = []

CODE_PATTERNS = [
    re.compile(r"\b(D-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(EXP-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(T-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(DOC-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(M-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(LOG-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(R-\d+)\b", re.IGNORECASE),
    re.compile(r"\b(CL-\d+)\b", re.IGNORECASE),
]

MODEL_MAP = {
    "model b": "MobileNetV3",
    "mobilenet": "MobileNetV3",
    "mobilenetv3": "MobileNetV3",
    "model a": "ResNet-18",
    "resnet": "ResNet",
    "resnet-18": "ResNet-18",
    "resnet18": "ResNet-18",
    "resnet-50": "ResNet-50",
    "resnet50": "ResNet-50",
    "model c": "ShuffleNetV2",
    "shufflenet": "ShuffleNetV2",
}

PEOPLE_NAMES = ["karan", "meera", "ananya", "vikram", "rohan"]

def detect_query_intent(query: str) -> QueryIntent:
    """
    Plan §4.2: Intent/entity detection for user query.
    Extracts explicit entity codes, architecture aliases, key people, and classifies intent.
    """
    q_lower = query.lower()
    
    # 1. Extract formal entity codes
    codes = set()
    for pattern in CODE_PATTERNS:
        matches = pattern.findall(query)
        for m in matches:
            codes.add(m.upper())

    # 2. Extract model references
    model_aliases = []
    for alias, canonical in MODEL_MAP.items():
        if alias in q_lower:
            model_aliases.append(canonical)
            # If "model b" is mentioned, add D-17 or EXP-06 as target hints
            if "mobilenet" in canonical.lower():
                codes.add("D-17")
                codes.add("EXP-06")

    # 3. Extract people mentions
    people_mentions = [name.capitalize() for name in PEOPLE_NAMES if name in q_lower]

    # 4. Classify intent
    intent_type = "general"
    if any(k in q_lower for k in ["decid", "why", "rationale", "chosen", "alternative", "architecture", "choice"]) or any(c.startswith("D-") for c in codes):
        intent_type = "decision"
    elif any(k in q_lower for k in ["experiment", "benchmark", "accuracy", "latency", "f1", "dataset", "test", "eval"]) or any(c.startswith("EXP-") for c in codes):
        intent_type = "experiment"
    elif any(k in q_lower for k in ["task", "who", "assign", "owner", "due", "deadline", "todo", "blocked"]) or any(c.startswith("T-") for c in codes):
        intent_type = "task"
    elif any(k in q_lower for k in ["contradict", "conflict", "discrepan", "sunlight", "degrad", "drop"]) or any(c.startswith("C-") for c in codes):
        intent_type = "contradiction"

    # 5. Extract significant keywords
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "why", "how", "who", "when", "where", "did", "we", "for", "in", "on", "to", "and", "or", "of", "with", "by", "at", "our", "this", "that"}
    words = re.findall(r"\b\w{2,}\b", q_lower)
    keywords = [w for w in words if w not in stop_words and not any(w == c.lower() for c in codes)]

    return QueryIntent(
        raw_query=query,
        intent_type=intent_type,
        entity_codes=sorted(list(codes)),
        keywords=keywords,
        model_aliases=list(set(model_aliases)),
        people_mentions=people_mentions,
    )

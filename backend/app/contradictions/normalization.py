import re
from typing import Dict, Any, Tuple

def get_normalized_claim_keys(claim: Any, alias_lookup: Dict[str, Dict[str, str]]) -> Tuple[str, str, str, float, str, str]:
    """
    Normalizes claim keys.
    Returns: (subject, metric, dataset, value, direction, condition)
    """
    def normalize_term(term: str, kind: str) -> str:
        if not term:
            return ""
        term_lower = term.lower().strip()
        kind_aliases = alias_lookup.get(kind, {})
        return kind_aliases.get(term_lower, term_lower)

    subj = normalize_term(getattr(claim, "subject", "") or "", "subject")
    metric = normalize_term(getattr(claim, "metric", "") or "", "metric")
    dataset = normalize_term(getattr(claim, "dataset", "") or "", "dataset")
    
    val = getattr(claim, "value", None)
    if val is None:
        val = 0.0
    
    direction = (getattr(claim, "direction", "") or "").lower().strip()
    condition = (getattr(claim, "condition", "") or "").lower().strip()
    
    return (subj, metric, dataset, float(val), direction, condition)

from typing import Optional
from app.models.entities import Claim
from app.schemas.contracts import ContradictionClassification
from app.contradictions.normalization import get_normalized_claim_keys

def check_rule_contradiction(claim_a: Claim, claim_b: Claim, alias_lookup: dict) -> Optional[ContradictionClassification]:
    keys_a = get_normalized_claim_keys(claim_a, alias_lookup)
    keys_b = get_normalized_claim_keys(claim_b, alias_lookup)
    
    subj_a, met_a, data_a, val_a, dir_a, cond_a = keys_a
    subj_b, met_b, data_b, val_b, dir_b, cond_b = keys_b
    
    if not subj_a or not met_a or subj_a != subj_b or met_a != met_b:
        return None
        
    is_contradiction = False
    explanation = ""
    
    # 1. Opposite direction
    opposites = {
        "greater_than": "less_than",
        "less_than": "greater_than",
        "increase": "decrease",
        "decrease": "increase",
        "better": "worse",
        "worse": "better"
    }
    if dir_a and dir_b and opposites.get(dir_a) == dir_b:
        is_contradiction = True
        explanation = f"Opposite directions for {met_a} on {subj_a} ({dir_a} vs {dir_b})."
        
    # 2. Value delta exceeds tolerance (absolute diff > 5.0 or relative diff > 0.05)
    # Actually prompt says: "> 5.0 or > 0.05 on normalized scale (e.g. 88.2% vs 78.5% or 91.2% vs 76.4%)"
    # Wait, the prompt specifically mentions: $|v_1 - v_2| > 5.0$ or $> 0.05$
    delta = abs(val_a - val_b)
    if delta > 5.0 or (val_a <= 1.0 and val_b <= 1.0 and delta > 0.05):
        if val_a != 0.0 and val_b != 0.0:
            is_contradiction = True
            explanation = f"Value delta {delta:.4f} exceeds tolerance for {met_a} on {subj_a}."
        
    # 3. Condition contrasts (e.g. benchmark/clean room vs harsh rural sunlight/field conditions)
    # The instructions say "if condition contrasts". Let's do simple keyword match.
    if cond_a and cond_b and cond_a != cond_b:
        contrast_words = ["vs", "benchmark", "clean", "harsh", "field", "rural"]
        if ("benchmark" in cond_a and "field" in cond_b) or ("benchmark" in cond_b and "field" in cond_a):
            is_contradiction = True
            explanation = f"Contrasting conditions: '{cond_a}' vs '{cond_b}'."

    # Need dataset check? Seeded EXP-09 conflict might be dataset or condition difference. Let's see. 
    # If same subject + metric, but the value is vastly different, that's caught by rule 2.
    
    if is_contradiction:
        return ContradictionClassification(
            is_contradiction=True,
            confidence=0.95,
            detection_method="rule",
            explanation=explanation,
            excerpt_a=claim_a.statement or claim_a.source_excerpt or "",
            excerpt_b=claim_b.statement or claim_b.source_excerpt or "",
            metric_delta=delta
        )
    return None

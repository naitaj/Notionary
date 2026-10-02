from rapidfuzz import fuzz
from app.schemas.contracts import ExtractionResult

def validate_excerpts(result: ExtractionResult, source_text: str) -> ExtractionResult:
    discarded = 0
    
    def is_valid(excerpt: str) -> bool:
        if not excerpt:
            return False
        if excerpt in source_text:
            return True
        ratio = fuzz.partial_ratio(excerpt.lower(), source_text.lower())
        return ratio >= 90
        
    valid_decisions = []
    for d in result.decisions:
        if is_valid(d.excerpt):
            valid_decisions.append(d)
        else:
            discarded += 1
    result.decisions = valid_decisions
    
    valid_tasks = []
    for t in result.tasks:
        if is_valid(t.excerpt):
            valid_tasks.append(t)
        else:
            discarded += 1
    result.tasks = valid_tasks
    
    valid_exps = []
    for e in result.experiments:
        if is_valid(e.excerpt):
            valid_exps.append(e)
        else:
            discarded += 1
    result.experiments = valid_exps
    
    valid_claims = []
    for c in result.claims:
        if is_valid(c.excerpt):
            valid_claims.append(c)
        else:
            discarded += 1
    result.claims = valid_claims
    
    result.discarded_excerpts_count += discarded
    return result

import json
from typing import Optional
from app.models.entities import Claim
from app.schemas.contracts import ContradictionClassification
from app.ai.providers.factory import get_llm_provider
from pydantic import BaseModel, Field

class LLMContradictionOutput(BaseModel):
    is_contradiction: bool
    confidence: float
    explanation: str
    needs_context: bool
    excerpt_a: str
    excerpt_b: str

async def classify_with_llm(claim_a: Claim, claim_b: Claim) -> Optional[ContradictionClassification]:
    provider = get_llm_provider()
    
    a_text = (claim_a.statement or "") + " " + (claim_a.source_excerpt or "")
    b_text = (claim_b.statement or "") + " " + (claim_b.source_excerpt or "")
    
    prompt = f"""
    Analyze if Claim A and Claim B contradict each other.
    Claim A: {a_text}
    Claim B: {b_text}
    
    Output strictly in JSON format matching the schema.
    """
    
    try:
        output = await provider.complete_structured(
            prompt=prompt,
            response_model=LLMContradictionOutput
        )
        
        if output.needs_context or not output.is_contradiction:
            return None
            
        # Validate verbatim citations
        if output.excerpt_a and output.excerpt_a not in a_text:
            return None
        if output.excerpt_b and output.excerpt_b not in b_text:
            return None
            
        return ContradictionClassification(
            is_contradiction=output.is_contradiction,
            confidence=output.confidence,
            detection_method="llm",
            explanation=output.explanation,
            excerpt_a=output.excerpt_a,
            excerpt_b=output.excerpt_b
        )
    except Exception as e:
        print(f"LLM Classification failed: {e}")
        return None

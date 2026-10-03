from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.contradictions.candidates import generate_candidates
from app.contradictions.rules import check_rule_contradiction
from app.contradictions.classifier import classify_with_llm
from app.contradictions.stale import detect_stale_documents
from app.models.entities import Contradiction
from app.ingestion.csv_mapper import ensure_dataset_aliases

async def run_contradiction_scan(db: AsyncSession, project_id: str) -> Dict[str, Any]:
    candidates = await generate_candidates(db, project_id)
    alias_lookup = await ensure_dataset_aliases(db, project_id)
    
    contradictions_found = 0
    pairs_evaluated = 0
    
    # Load existing to avoid duplicates
    existing_res = await db.execute(select(Contradiction).where(Contradiction.project_id == project_id))
    existing = set()
    for c in existing_res.scalars().all():
        existing.add(tuple(sorted([c.a_id, c.b_id])))
    
    for claim_a, claim_b, c_type in candidates:
        pair_id = tuple(sorted([claim_a.id, claim_b.id]))
        if pair_id in existing:
            continue
            
        pairs_evaluated += 1
        
        # Rule check first
        classification = check_rule_contradiction(claim_a, claim_b, alias_lookup)
        
        # Fallback to LLM if rule didn't catch it and candidates were semantically matched
        # Or always fallback? "Only use LLM pair classifier on candidates lacking structure."
        if not classification and c_type == "semantic":
            classification = await classify_with_llm(claim_a, claim_b)
            
        if classification and classification.is_contradiction:
            c = Contradiction(
                project_id=project_id,
                a_type="claim",
                a_id=claim_a.id,
                b_type="claim",
                b_id=claim_b.id,
                detection_method=classification.detection_method,
                status="open",
                explanation=classification.explanation,
                excerpt_a_id=claim_a.source_excerpt_id,
                excerpt_b_id=claim_b.source_excerpt_id,
                llm_result={
                    "confidence": classification.confidence,
                    "excerpt_a": classification.excerpt_a,
                    "excerpt_b": classification.excerpt_b,
                    "metric_delta": classification.metric_delta
                }
            )
            db.add(c)
            existing.add(pair_id)
            contradictions_found += 1
            
    # Run stale detection
    stale_flags = await detect_stale_documents(db, project_id)
    stale_docs_found = len(stale_flags)
    
    await db.commit()
    
    return {
        "contradictions_found": contradictions_found,
        "stale_docs_found": stale_docs_found,
        "pairs_evaluated": pairs_evaluated
    }

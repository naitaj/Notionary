from typing import List, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import Claim
from app.contradictions.normalization import get_normalized_claim_keys
from app.ingestion.csv_mapper import ensure_dataset_aliases
import numpy as np
import json

def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    v1 = np.array(v1)
    v2 = np.array(v2)
    norm = np.linalg.norm(v1) * np.linalg.norm(v2)
    if norm == 0:
        return 0.0
    return np.dot(v1, v2) / norm

async def generate_candidates(db: AsyncSession, project_id: str) -> List[Tuple[Claim, Claim, str]]:
    result = await db.execute(select(Claim).where(Claim.project_id == project_id))
    claims = result.scalars().all()
    
    alias_lookup = await ensure_dataset_aliases(db, project_id)
    
    candidates = []
    seen = set()
    
    for i, claim_a in enumerate(claims):
        keys_a = get_normalized_claim_keys(claim_a, alias_lookup)
        subj_a, met_a = keys_a[0], keys_a[1]
        
        for j in range(i + 1, len(claims)):
            claim_b = claims[j]
            keys_b = get_normalized_claim_keys(claim_b, alias_lookup)
            subj_b, met_b = keys_b[0], keys_b[1]
            
            pair_id = tuple(sorted([claim_a.id, claim_b.id]))
            if pair_id in seen:
                continue
                
            # Strategy 1: Structured key match
            if subj_a and met_a and subj_a == subj_b and met_a == met_b:
                candidates.append((claim_a, claim_b, "structured"))
                seen.add(pair_id)
                continue
                
            # Strategy 2: Embedding similarity
            if claim_a.embedding and claim_b.embedding:
                try:
                    sim = cosine_similarity(claim_a.embedding, claim_b.embedding)
                    if sim > 0.85:  # threshold for high semantic overlap
                        candidates.append((claim_a, claim_b, "semantic"))
                        seen.add(pair_id)
                except Exception:
                    pass

    return candidates

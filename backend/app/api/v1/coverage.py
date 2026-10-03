"""
Phase 8 — Claim Coverage & Missing Evidence API (PRD §14.4 / Plan §8.2)

Endpoints:
  GET /coverage/projects/{project_id} — full project claim coverage checklist report
  GET /coverage/claims/{claim_id}     — individual claim sufficiency profile
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.entities import Claim
from app.schemas.contracts import CoverageResult
from app.intelligence.coverage import evaluate_claim_coverage, get_project_coverage

router = APIRouter(prefix="/coverage", tags=["Coverage & Missing Evidence"])


@router.get("/projects/{project_id}", response_model=List[CoverageResult])
async def get_project_claims_coverage(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve coverage and sufficiency profiles for all claims in a project."""
    return await get_project_coverage(db, project_id)


@router.get("/claims/{claim_id}", response_model=CoverageResult)
async def get_claim_coverage_endpoint(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve checklist-based sufficiency profile for a specific claim."""
    res = await db.execute(select(Claim).where(Claim.id == claim_id))
    claim = res.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return await evaluate_claim_coverage(db, claim)

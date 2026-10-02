from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Contradiction, Claim

router = APIRouter(prefix="/contradictions", tags=["Contradiction Radar"])

class ContradictionResponse(BaseModel):
    id: str
    project_id: str
    claim_a_id: str
    claim_b_id: str
    claim_a_text: Optional[str] = None
    claim_b_text: Optional[str] = None
    detection_method: str
    status: str
    explanation: Optional[str] = None

class ContradictionResolve(BaseModel):
    status: str  # confirmed, dismissed, context_differs
    resolution_notes: Optional[str] = None

@router.get("", response_model=List[ContradictionResponse])
async def list_contradictions(project_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Contradiction)
    if project_id:
        stmt = stmt.where(Contradiction.project_id == project_id)
    res = await db.execute(stmt)
    contras = res.scalars().all()

    output = []
    for c in contras:
        c_a = await db.execute(select(Claim).where(Claim.id == c.claim_a_id))
        claim_a = c_a.scalar_one_or_none()
        c_b = await db.execute(select(Claim).where(Claim.id == c.claim_b_id))
        claim_b = c_b.scalar_one_or_none()

        output.append(ContradictionResponse(
            id=c.id,
            project_id=c.project_id,
            claim_a_id=c.claim_a_id,
            claim_b_id=c.claim_b_id,
            claim_a_text=claim_a.statement if claim_a else "Claim A",
            claim_b_text=claim_b.statement if claim_b else "Claim B",
            detection_method=c.detection_method,
            status=c.status,
            explanation=c.explanation,
        ))
    return output

@router.post("/{contradiction_id}/resolve")
async def resolve_contradiction(contradiction_id: str, data: ContradictionResolve, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Contradiction).where(Contradiction.id == contradiction_id))
    contra = res.scalar_one_or_none()
    if not contra:
        raise HTTPException(status_code=404, detail="Contradiction not found")
    contra.status = data.status
    if data.resolution_notes:
        contra.explanation = (contra.explanation or "") + f" [Resolved: {data.resolution_notes}]"
    await db.commit()
    return {"status": "success", "contradiction_id": contradiction_id, "new_status": contra.status}

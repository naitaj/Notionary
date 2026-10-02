from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Claim

router = APIRouter(prefix="/claims", tags=["Claims & Evidence"])

class ClaimCreate(BaseModel):
    project_id: str
    statement: str
    claim_type: Optional[str] = "observation"
    subject: Optional[str] = None
    metric: Optional[str] = None
    direction: Optional[str] = None
    dataset: Optional[str] = None
    status: Optional[str] = "unverified"
    source_excerpt: Optional[str] = None

class ClaimResponse(BaseModel):
    id: str
    project_id: str
    statement: str
    claim_type: str
    subject: Optional[str] = None
    metric: Optional[str] = None
    direction: Optional[str] = None
    dataset: Optional[str] = None
    status: str
    source_excerpt: Optional[str] = None
    notion_url: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[ClaimResponse])
async def list_claims(project_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Claim)
    if project_id:
        stmt = stmt.where(Claim.project_id == project_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=ClaimResponse)
async def create_claim(data: ClaimCreate, db: AsyncSession = Depends(get_db)):
    claim = Claim(
        project_id=data.project_id,
        statement=data.statement,
        claim_type=data.claim_type or "observation",
        subject=data.subject,
        metric=data.metric,
        direction=data.direction,
        dataset=data.dataset,
        status=data.status or "unverified",
        source_excerpt=data.source_excerpt,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)
    return claim

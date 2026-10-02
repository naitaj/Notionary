from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel

from app.database import get_db
from app.models.entities import Proposal, Decision, Task, Experiment, Claim, Edge, AuditLog
from app.schemas.contracts import ProposalPayload
from workers.runner import enqueue_job

router = APIRouter()

class RejectRequest(BaseModel):
    reason: str

class BulkApproveRequest(BaseModel):
    project_id: str
    proposal_ids: List[str]

@router.get("/", response_model=List[ProposalPayload])
async def list_proposals(
    project_id: str,
    status: str = "pending",
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Proposal).where(Proposal.project_id == project_id, Proposal.status == status)
    result = await db.execute(stmt)
    proposals = result.scalars().all()
    
    return [
        ProposalPayload(
            id=p.id,
            project_id=p.project_id,
            entity_type=p.entity_type,
            tier=p.tier,
            confidence_label=p.confidence_label,
            needs_attention=p.needs_attention,
            status=p.status,
            payload=p.payload,
            excerpt_text=p.payload.get("excerpt"),
            created_at=p.created_at
        )
        for p in proposals
    ]

@router.patch("/{proposal_id}", response_model=ProposalPayload)
async def update_proposal(
    proposal_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Proposal).where(Proposal.id == proposal_id)
    res = await db.execute(stmt)
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    p.payload = payload
    await db.commit()
    await db.refresh(p)
    
    return ProposalPayload(
        id=p.id,
        project_id=p.project_id,
        entity_type=p.entity_type,
        tier=p.tier,
        confidence_label=p.confidence_label,
        needs_attention=p.needs_attention,
        status=p.status,
        payload=p.payload,
        excerpt_text=p.payload.get("excerpt"),
        created_at=p.created_at
    )

async def _approve_proposal(db: AsyncSession, p: Proposal):
    pl = p.payload
    entity = None
    if p.entity_type == "decision":
        entity = Decision(
            id=str(uuid4()),
            project_id=p.project_id,
            code=pl["code"],
            statement=pl["statement"],
            rationale=pl.get("rationale"),
            origin="system_derived"
        )
    elif p.entity_type == "task":
        entity = Task(
            id=str(uuid4()),
            project_id=p.project_id,
            code=pl.get("code"),
            title=pl["title"],
            origin="system_derived"
        )
    elif p.entity_type == "experiment":
        entity = Experiment(
            id=str(uuid4()),
            project_id=p.project_id,
            code=pl["code"],
            hypothesis=pl.get("hypothesis"),
            origin="system_derived"
        )
    elif p.entity_type == "claim":
        entity = Claim(
            id=str(uuid4()),
            project_id=p.project_id,
            statement=pl["statement"],
            origin="system_derived"
        )
        
    if entity:
        db.add(entity)
        
    audit = AuditLog(
        project_id=p.project_id,
        action="approve_proposal",
        entity_type=p.entity_type,
        entity_id=entity.id if entity else p.id,
        after_state=pl
    )
    db.add(audit)
    
    p.status = "approved"
    
    if entity:
        await enqueue_job(
            db, "notion_sync_push",
            payload={"entity_type": p.entity_type, "entity_id": entity.id},
            project_id=p.project_id
        )

@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Proposal).where(Proposal.id == proposal_id)
    res = await db.execute(stmt)
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    await _approve_proposal(db, p)
    await db.commit()
    return {"status": "ok"}
    
@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Proposal).where(Proposal.id == proposal_id)
    res = await db.execute(stmt)
    p = res.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    p.status = "rejected"
    p.rejection_reason = req.reason
    await db.commit()
    return {"status": "ok"}
    
@router.post("/bulk-approve")
async def bulk_approve(
    req: BulkApproveRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Proposal).where(Proposal.id.in_(req.proposal_ids), Proposal.project_id == req.project_id)
    res = await db.execute(stmt)
    proposals = res.scalars().all()
    
    for p in proposals:
        if p.tier == "high":
            raise HTTPException(status_code=400, detail="Cannot bulk approve high tier proposals")
            
    for p in proposals:
        await _approve_proposal(db, p)
        
    await db.commit()
    return {"status": "ok", "count": len(proposals)}

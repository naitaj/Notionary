from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database import get_db
from app.models.entities import Edge, AuditLog
from app.core.auth import get_current_user, UserContext

router = APIRouter(prefix="/edges", tags=["Edges"])

class EdgeCreate(BaseModel):
    project_id: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    edge_type: str
    origin: Optional[str] = "human_authored"
    rationale_text: Optional[str] = None

class EdgeResponse(BaseModel):
    id: str
    project_id: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    edge_type: str
    origin: str
    review_status: str
    rationale_text: Optional[str] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.post("", response_model=EdgeResponse)
async def create_edge(
    data: EdgeCreate, 
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    review_status = "unreviewed" if data.origin == "ai_inferred" else "approved"
    edge = Edge(
        project_id=data.project_id,
        from_type=data.from_type,
        from_id=data.from_id,
        to_type=data.to_type,
        to_id=data.to_id,
        edge_type=data.edge_type,
        origin=data.origin or "human_authored",
        review_status=review_status,
        rationale_text=data.rationale_text,
        effective_from=datetime.now(timezone.utc)
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge

@router.get("", response_model=List[EdgeResponse])
async def list_edges(
    project_id: Optional[str] = None,
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Edge)
    if project_id:
        stmt = stmt.where(Edge.project_id == project_id)
    if from_id:
        stmt = stmt.where(Edge.from_id == from_id)
    if to_id:
        stmt = stmt.where(Edge.to_id == to_id)
        
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{edge_id}/approve", response_model=EdgeResponse)
async def approve_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    result = await db.execute(select(Edge).where(Edge.id == edge_id))
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
        
    edge.review_status = "approved"
    
    # Audit log
    audit = AuditLog(
        project_id=edge.project_id,
        actor_id=user.id,
        actor_type="human",
        action="approve",
        entity_type="edge",
        entity_id=edge.id,
        before_state={"review_status": "unreviewed"},
        after_state={"review_status": "approved"}
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(edge)
    return edge

@router.post("/{edge_id}/retire", response_model=EdgeResponse)
async def retire_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    result = await db.execute(select(Edge).where(Edge.id == edge_id))
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
        
    now = datetime.now(timezone.utc)
    edge.effective_to = now
    
    # Audit log
    audit = AuditLog(
        project_id=edge.project_id,
        actor_id=user.id,
        actor_type="human",
        action="retire",
        entity_type="edge",
        entity_id=edge.id,
        after_state={"effective_to": now.isoformat()}
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(edge)
    return edge

@router.delete("/{edge_id}")
async def delete_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    # Admin only (checking role in real app, we mock here or just allow)
    result = await db.execute(select(Edge).where(Edge.id == edge_id))
    edge = result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
        
    await db.delete(edge)
    await db.commit()
    return {"status": "deleted"}

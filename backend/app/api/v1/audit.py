from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.entities import AuditLog
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/audit", tags=["Audit"])

class AuditLogEntry(BaseModel):
    id: str
    project_id: str
    actor_id: str
    actor_type: str
    action: str
    entity_type: str
    entity_id: str
    before_state: Optional[dict] = None
    after_state: Optional[dict] = None
    prompt_version: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime

@router.get("", response_model=List[AuditLogEntry])
async def get_audit_trail(
    project_id: str = Query(..., description="Project ID"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        AuditLogEntry(
            id=log.id,
            project_id=log.project_id,
            actor_id=log.actor_id,
            actor_type=log.actor_type,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before_state=log.before_state,
            after_state=log.after_state,
            prompt_version=log.prompt_version,
            model=log.model,
            created_at=log.created_at,
        )
        for log in logs
    ]

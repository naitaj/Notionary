from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import AuditLog

async def log_audit_event(
    db: AsyncSession,
    project_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str = "system",
    actor_type: str = "system",
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    prompt_version: Optional[str] = None,
    model: Optional[str] = None,
) -> AuditLog:
    """Creates an append-only audit trail entry for traceability and compliance."""
    log_entry = AuditLog(
        project_id=project_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
        prompt_version=prompt_version,
        model=model,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    await db.flush()
    return log_entry

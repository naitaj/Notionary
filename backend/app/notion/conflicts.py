from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import NotionConflict, Decision, Task, Claim, Experiment
from app.notion.push import MODEL_MAP, push_entity_to_notion
from app.core.errors import ProblemException

async def list_conflicts(db: AsyncSession, project_id: str) -> List[NotionConflict]:
    stmt = (
        select(NotionConflict)
        .where(NotionConflict.project_id == project_id, NotionConflict.status == "open")
        .order_by(NotionConflict.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()

async def resolve_conflict(
    db: AsyncSession,
    conflict_id: str,
    resolution_choice: str,  # "notion_wins", "app_wins"
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    stmt = select(NotionConflict).where(NotionConflict.id == conflict_id)
    res = await db.execute(stmt)
    conflict = res.scalars().first()
    if not conflict:
        raise ProblemException(status=404, title="Conflict Not Found", detail="The specified sync conflict does not exist.")

    model_cls = MODEL_MAP.get(conflict.entity_type.lower())
    if not model_cls:
        raise ProblemException(status=400, title="Unsupported Entity", detail=f"No model for {conflict.entity_type}")

    rec_res = await db.execute(select(model_cls).where(model_cls.id == conflict.entity_id))
    record = rec_res.scalars().first()

    now = datetime.now(timezone.utc)
    if resolution_choice == "notion_wins" and record:
        # Notion wins: update local record with notion snapshot properties
        record.local_dirty = False
        record.sync_status = "synced"
    elif resolution_choice == "app_wins" and record:
        # App wins: re-push local record to Notion
        record.local_dirty = False
        record.sync_status = "pending"
        await push_entity_to_notion(db, conflict.project_id, conflict.entity_type, record.id)

    conflict.status = "resolved"
    conflict.resolution = {"choice": resolution_choice, "resolved_at": now.isoformat()}
    conflict.resolved_by = user_id
    conflict.resolved_at = now
    await db.commit()

    return {"status": "resolved", "conflict_id": conflict.id, "choice": resolution_choice}

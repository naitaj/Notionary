from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Project, NotionDatabase, NotionConflict, Decision, Task, Claim, Experiment
from app.notion.client import get_notion_client, NotionClient
from app.notion.bootstrap import bootstrap_workspace
from app.notion.push import push_all_pending, push_entity_to_notion
from app.notion.poll import poll_all_databases
from app.notion.conflicts import list_conflicts, resolve_conflict
from app.core.errors import ProblemException

router = APIRouter(prefix="/notion", tags=["Notion Integration"])

class NotionConnectRequest(BaseModel):
    project_id: str
    api_key: Optional[str] = None
    parent_page_id: str

class NotionBootstrapResponse(BaseModel):
    status: str
    message: str
    created_databases: Dict[str, str]

class ConflictResolutionRequest(BaseModel):
    choice: str = "notion_wins"  # notion_wins or app_wins

@router.post("/connect")
async def connect_notion(data: NotionConnectRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Project).where(Project.id == data.project_id))
    project = res.scalars().first()
    if not project:
        raise ProblemException(status=404, title="Project Not Found", detail=f"Project '{data.project_id}' not found.")
    
    # Validate parent page access with Notion client
    client = NotionClient(api_key=data.api_key)
    try:
        page_info = await client.get_page(data.parent_page_id)
    except Exception as e:
        raise ProblemException(status=400, title="Notion Connection Error", detail=f"Could not access Notion parent page: {str(e)}")

    project.notion_parent_id = data.parent_page_id
    await db.commit()
    return {
        "status": "connected",
        "parent_page_id": data.parent_page_id,
        "is_mock": client.is_mock,
    }

@router.post("/{project_id}/bootstrap", response_model=NotionBootstrapResponse)
async def bootstrap_notion(project_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Project).where(Project.id == project_id))
    project = res.scalars().first()
    if not project:
        raise ProblemException(status=404, title="Project Not Found", detail="Project not found.")

    parent_page_id = project.notion_parent_id or "notion-root-page"
    client = get_notion_client()
    created_dbs = await bootstrap_workspace(
        db=db,
        project_id=project_id,
        parent_page_id=parent_page_id,
        client=client,
    )
    return NotionBootstrapResponse(
        status="success",
        message="Successfully bootstrapped 11 relation-linked databases in Notion workspace",
        created_databases=created_dbs,
    )

@router.post("/{project_id}/sync/push")
async def sync_push(project_id: str, db: AsyncSession = Depends(get_db)):
    """Pushes all pending or dirty app records to Notion."""
    client = get_notion_client()
    results = await push_all_pending(db, project_id, client=client)
    return {
        "status": "completed",
        "pushed_count": results["pushed_count"],
        "errors": results["errors"],
    }

@router.post("/{project_id}/sync/poll")
async def sync_poll(project_id: str, db: AsyncSession = Depends(get_db)):
    """Polls Notion databases for changes and executes version bump / impact enqueue on changes."""
    client = get_notion_client()
    results = await poll_all_databases(db, project_id, client=client)
    return results

@router.post("/{project_id}/sync/now")
async def sync_now(project_id: str, db: AsyncSession = Depends(get_db)):
    """Executes a full bidirectional push + poll sync cycle."""
    client = get_notion_client()
    push_res = await push_all_pending(db, project_id, client=client)
    poll_res = await poll_all_databases(db, project_id, client=client)
    return {
        "status": "completed",
        "pushed_count": push_res["pushed_count"],
        "pulled_updated": poll_res["total_updated"],
        "conflicts": poll_res["total_conflicts"],
    }

@router.get("/{project_id}/status")
async def get_sync_status(project_id: str, db: AsyncSession = Depends(get_db)):
    # Fetch registered databases
    stmt = select(NotionDatabase).where(NotionDatabase.project_id == project_id)
    res = await db.execute(stmt)
    dbs = res.scalars().all()

    # Count pending syncs
    pending_decisions = await db.scalar(select(func.count()).select_from(Decision).where(Decision.project_id == project_id, Decision.sync_status == "pending"))
    pending_tasks = await db.scalar(select(func.count()).select_from(Task).where(Task.project_id == project_id, Task.sync_status == "pending"))
    conflicts_count = await db.scalar(select(func.count()).select_from(NotionConflict).where(NotionConflict.project_id == project_id, NotionConflict.status == "open"))

    return {
        "is_connected": True,
        "sync_mode": "bidirectional_polling",
        "poll_interval_seconds": 30,
        "database_count": len(dbs),
        "databases": [
            {"entity_type": d.entity_type, "notion_database_id": d.notion_database_id, "last_cursor": d.last_cursor}
            for d in dbs
        ],
        "pending_sync": (pending_decisions or 0) + (pending_tasks or 0),
        "conflicts_count": conflicts_count or 0,
    }

@router.get("/{project_id}/conflicts")
async def get_conflicts(project_id: str, db: AsyncSession = Depends(get_db)):
    conflicts = await list_conflicts(db, project_id)
    return conflicts

@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict_endpoint(
    conflict_id: str,
    data: ConflictResolutionRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await resolve_conflict(
        db=db,
        conflict_id=conflict_id,
        resolution_choice=data.choice,
    )
    return result

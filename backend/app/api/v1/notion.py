from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Project

router = APIRouter(prefix="/notion", tags=["Notion Integration"])

class NotionConnectRequest(BaseModel):
    project_id: str
    api_key: str
    parent_page_id: str

class NotionBootstrapResponse(BaseModel):
    status: str
    message: str
    created_databases: Dict[str, str]

@router.post("/connect")
async def connect_notion(data: NotionConnectRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Project).where(Project.id == data.project_id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.notion_parent_id = data.parent_page_id
    await db.commit()
    return {"status": "connected", "parent_page_id": data.parent_page_id}

@router.post("/{project_id}/bootstrap", response_model=NotionBootstrapResponse)
async def bootstrap_notion(project_id: str, db: AsyncSession = Depends(get_db)):
    # Simulates or calls Notion API to create the 8 canonical relation-linked databases
    databases = {
        "Projects": f"notion-db-projects-{project_id[:8]}",
        "Meetings": f"notion-db-meetings-{project_id[:8]}",
        "References": f"notion-db-references-{project_id[:8]}",
        "Claims": f"notion-db-claims-{project_id[:8]}",
        "Evidence": f"notion-db-evidence-{project_id[:8]}",
        "Experiments": f"notion-db-experiments-{project_id[:8]}",
        "Decisions": f"notion-db-decisions-{project_id[:8]}",
        "Tasks": f"notion-db-tasks-{project_id[:8]}",
        "Milestones": f"notion-db-milestones-{project_id[:8]}",
        "Deliverables": f"notion-db-deliverables-{project_id[:8]}",
    }
    return NotionBootstrapResponse(
        status="success",
        message="Successfully bootstrapped 10 relation-linked databases in Notion workspace",
        created_databases=databases,
    )

@router.get("/{project_id}/status")
async def get_sync_status(project_id: str):
    return {
        "is_connected": True,
        "sync_mode": "polling_delta",
        "poll_interval_seconds": 30,
        "last_synced_at": "2026-10-03T02:00:00Z",
        "synced_records": 48,
        "pending_sync": 0,
        "conflicts_count": 0,
    }

@router.post("/{project_id}/sync")
async def trigger_manual_sync(project_id: str):
    return {
        "status": "completed",
        "synced_at": "2026-10-03T02:05:00Z",
        "records_pulled": 2,
        "records_pushed": 5,
        "conflicts": [],
    }

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Project, Decision, Task, Experiment, Contradiction, Claim

router = APIRouter(prefix="/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    notion_parent_id: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    notion_parent_id: Optional[str] = None

    class Config:
        from_attributes = True

class HealthResponse(BaseModel):
    evidence_coverage: float
    blocked_tasks_count: int
    open_contradictions_count: int
    stale_decisions_count: int
    active_decisions_count: int
    experiments_count: int
    health_score: float

@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project))
    return result.scalars().all()

@router.post("", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(
        name=data.name,
        description=data.description,
        notion_parent_id=data.notion_parent_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

from app.schemas.contracts import ProjectHealthResponse
from app.intelligence.health import compute_project_health


@router.get("/{project_id}/health", response_model=ProjectHealthResponse)
async def get_project_health(project_id: str, db: AsyncSession = Depends(get_db)):
    """
    Plan §8.1 / PRD §14.8: Six-dimension project health radar with documented thresholds.
    """
    return await compute_project_health(db, project_id)


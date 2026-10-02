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

@router.get("/{project_id}/health", response_model=HealthResponse)
async def get_project_health(project_id: str, db: AsyncSession = Depends(get_db)):
    # Tasks
    tasks_res = await db.execute(select(Task).where(Task.project_id == project_id))
    tasks = tasks_res.scalars().all()
    blocked_tasks = sum(1 for t in tasks if t.is_blocked or t.status == "blocked")

    # Contradictions
    contra_res = await db.execute(select(Contradiction).where(Contradiction.project_id == project_id))
    contras = contra_res.scalars().all()
    open_contras = sum(1 for c in contras if c.status == "open")

    # Decisions
    dec_res = await db.execute(select(Decision).where(Decision.project_id == project_id))
    decisions = dec_res.scalars().all()
    active_decisions = sum(1 for d in decisions if d.status == "active")

    # Claims coverage
    claims_res = await db.execute(select(Claim).where(Claim.project_id == project_id))
    claims = claims_res.scalars().all()
    supported_claims = sum(1 for c in claims if c.status == "supported")
    total_claims = len(claims)
    coverage = (supported_claims / total_claims * 100.0) if total_claims > 0 else 100.0

    # Experiments
    exp_res = await db.execute(select(Experiment).where(Experiment.project_id == project_id))
    experiments = exp_res.scalars().all()

    # Derived health score (0-100)
    score = max(0.0, min(100.0, 100.0 - (blocked_tasks * 8.0) - (open_contras * 12.0) + (coverage * 0.2)))

    return HealthResponse(
        evidence_coverage=round(coverage, 1),
        blocked_tasks_count=blocked_tasks,
        open_contradictions_count=open_contras,
        stale_decisions_count=0,
        active_decisions_count=active_decisions,
        experiments_count=len(experiments),
        health_score=round(score, 1),
    )

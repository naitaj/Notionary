from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.entities import Task, Decision
from app.graph.traversal import traverse_graph
from app.core.auth import get_current_user, UserContext, UserScope

router = APIRouter(prefix="/tasks", tags=["Tasks"])

class TaskCreate(BaseModel):
    project_id: str
    code: str
    title: str
    owner: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "todo"
    origin_decision_id: Optional[str] = None
    is_blocked: Optional[bool] = False
    blocked_reason: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    project_id: str
    code: str
    title: str
    status: str
    owner: Optional[str] = None
    priority: str
    origin_decision_id: Optional[str] = None
    is_blocked: bool
    blocked_reason: Optional[str] = None
    notion_url: Optional[str] = None

    class Config:
        from_attributes = True

class TaskContextResponse(BaseModel):
    task: TaskResponse
    origin_decision: Optional[dict] = None
    why_explanation: str
    chain: List[dict]

@router.get("", response_model=List[TaskResponse])
async def list_tasks(project_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Task)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=TaskResponse)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(
        project_id=data.project_id,
        code=data.code,
        title=data.title,
        owner=data.owner,
        priority=data.priority or "medium",
        status=data.status or "todo",
        origin_decision_id=data.origin_decision_id,
        is_blocked=data.is_blocked or False,
        blocked_reason=data.blocked_reason,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@router.get("/{task_id}/context", response_model=TaskContextResponse)
async def get_task_context(
    task_id: str, 
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    role = user.roles_by_project.get(task.project_id, "member")
    team_ids = user.teams_by_project.get(task.project_id, [])
    scope = UserScope(user_id=user.id, project_id=task.project_id, role=role, team_ids=team_ids)

    # Traverse reverse to find origin chain
    nodes, edges = await traverse_graph(
        db=db,
        project_id=task.project_id,
        start_id=task.id,
        direction="reverse",
        max_depth=3,
        scope=scope
    )

    decision_dict = None
    why_text = "This task was created directly as an execution deliverable."
    chain = []
    
    # Try to find a decision in the nodes
    decisions = [n for n in nodes if n.entity_type == "decision"]
    if decisions:
        d = decisions[0]
        decision_dict = {
            "id": d.id,
            "code": d.code,
            "statement": d.title,
        }
        why_text = f"Originates from Decision {d.code}: '{d.title}'."

    # Build chain
    for n in nodes:
        if n.id != task.id:
            chain.append({
                "id": n.id,
                "type": n.entity_type,
                "title": n.title
            })

    return TaskContextResponse(
        task=TaskResponse.model_validate(task),
        origin_decision=decision_dict,
        why_explanation=why_text,
        chain=chain
    )


@router.get("/{task_id}/blocked-status")
async def get_task_blocked_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Plan §8.5: Rule-based derivation of task blockage.
    Checks manual override, upstream incomplete tasks, and foundation decision status.
    """
    from app.graph.blocked_tasks import derive_task_blockage

    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return await derive_task_blockage(db, task)


@router.get("/project/{project_id}/blocked")
async def get_project_blocked_tasks(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Derive blockage for all tasks in a project."""
    from app.graph.blocked_tasks import derive_all_project_tasks_blockage

    return await derive_all_project_tasks_blockage(db, project_id)


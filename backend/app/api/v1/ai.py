from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.entities import EvalRun
from app.schemas.contracts import RagQueryRequest, RagAnswer
from app.core.auth import UserScope, get_current_user, UserContext
from app.rag.engine import execute_rag_query
from app.rag.eval import run_golden_qa_eval, seed_golden_eval_cases

router = APIRouter(prefix="/ai", tags=["AI Reasoning & Cited Q&A"])

class QueryRequest(BaseModel):
    project_id: str
    query: str
    as_of: Optional[str] = None

class EvalRunResponse(BaseModel):
    id: str
    project_id: str
    eval_type: str
    git_sha: Optional[str] = None
    prompt_version: Optional[str] = None
    model: Optional[str] = None
    total_cases: int
    passed_cases: int
    hit_at_5: float
    citation_correctness: float
    metrics: Dict[str, Any]
    created_at: Any

    class Config:
        from_attributes = True

@router.post("/query", response_model=RagAnswer)
async def ask_assistant(
    data: QueryRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Plan §4.7: POST /ai/query.
    Evidence-grounded, cited Q&A engine with strict permissions filtering and refusal guardrails.
    """
    user_role = user.roles_by_project.get(data.project_id) or user.roles_by_project.get("*", "member")
    team_ids = user.teams_by_project.get(data.project_id) or user.teams_by_project.get("*", [])
    
    scope = UserScope(
        user_id=user.id,
        project_id=data.project_id,
        role=user_role,
        team_ids=team_ids,
    )

    answer = await execute_rag_query(
        db=db,
        project_id=data.project_id,
        query=data.query,
        scope=scope,
        as_of=data.as_of,
    )
    return answer

@router.post("/eval/run", response_model=EvalRunResponse)
async def run_evaluation(
    project_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Plan §4.9: Run Golden Q&A evaluation benchmark (10 test cases) and record results.
    """
    user_role = user.roles_by_project.get(project_id) or user.roles_by_project.get("*", "owner")
    team_ids = user.teams_by_project.get(project_id) or user.teams_by_project.get("*", ["team_ml", "team_edge"])
    
    scope = UserScope(
        user_id=user.id,
        project_id=project_id,
        role=user_role,
        team_ids=team_ids,
    )

    await seed_golden_eval_cases(db, project_id)
    eval_run = await run_golden_qa_eval(db=db, project_id=project_id, scope=scope)
    return eval_run

@router.get("/eval/runs", response_model=List[EvalRunResponse])
async def list_evaluation_runs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Plan §4.9: Retrieve history of Golden Q&A evaluation runs.
    """
    stmt = (
        select(EvalRun)
        .where(EvalRun.project_id == project_id)
        .order_by(EvalRun.created_at.desc())
        .limit(10)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

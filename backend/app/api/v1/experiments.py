from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Experiment, ExperimentResult

router = APIRouter(prefix="/experiments", tags=["Experiments"])

class ExperimentCreate(BaseModel):
    project_id: str
    code: str
    hypothesis: Optional[str] = None
    model: Optional[str] = None
    dataset: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    owner: Optional[str] = None
    status: Optional[str] = "completed"

class ExperimentResponse(BaseModel):
    id: str
    project_id: str
    code: str
    hypothesis: Optional[str] = None
    model: Optional[str] = None
    dataset: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    status: str
    owner: Optional[str] = None
    notion_url: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[ExperimentResponse])
async def list_experiments(project_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Experiment)
    if project_id:
        stmt = stmt.where(Experiment.project_id == project_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=ExperimentResponse)
async def create_experiment(data: ExperimentCreate, db: AsyncSession = Depends(get_db)):
    exp = Experiment(
        project_id=data.project_id,
        code=data.code,
        hypothesis=data.hypothesis,
        model=data.model,
        dataset=data.dataset,
        parameters=data.parameters or {},
        owner=data.owner,
        status=data.status or "completed",
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return exp

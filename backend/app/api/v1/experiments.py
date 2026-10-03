from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Experiment, ExperimentResult
from app.schemas.contracts import ExperimentSummaryResponse

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


@router.get("/{experiment_id}/summary", response_model=ExperimentSummaryResponse)
async def get_experiment_summary(experiment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Plan §8.4 / PRD §14.6: Structured experiment summary.
    Numbers are copied directly from result rows; prose is labeled AI summary.
    """
    from app.models.entities import Edge, Decision
    from app.schemas.contracts import ExperimentSummaryResponse

    res = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    exp = res.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Fetch result rows
    r_res = await db.execute(
        select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id)
    )
    results = r_res.scalars().all()
    results_table = [
        {
            "metric": r.metric,
            "value": r.value,
            "unit": r.unit,
            "split": r.split,
            "num_runs": r.num_runs,
            "variance": r.variance,
            "baseline_ref": r.baseline_ref,
            "source_excerpt": r.source_excerpt,
        }
        for r in results
    ]

    # Baseline comparison summary
    baseline_diffs = {}
    for r in results:
        if r.baseline_ref:
            baseline_diffs[r.metric] = {
                "value": r.value,
                "baseline": r.baseline_ref,
                "split": r.split,
            }

    # Find linked decisions via edges
    result_ids = [r.id for r in results]
    edge_clauses = [Edge.from_id == experiment_id]
    if result_ids:
        edge_clauses.append(Edge.from_id.in_(result_ids))
    edge_res = await db.execute(
        select(Edge).where(
            or_(*edge_clauses),
            Edge.to_type == "decision",
            Edge.effective_to.is_(None),
        )
    )
    edges = edge_res.scalars().all()
    dec_ids = [e.to_id for e in edges]
    linked_decisions = []
    if dec_ids:
        dec_res = await db.execute(select(Decision).where(Decision.id.in_(dec_ids)))
        linked_decisions = [
            {"id": d.id, "code": d.code, "statement": d.statement, "status": d.status}
            for d in dec_res.scalars().all()
        ]

    # AI summary prose
    metrics_summary = ", ".join(f"{r.metric}: {r.value}{r.unit or ''}" for r in results) or "No metrics logged"
    ai_summary = (
        f"[AI summary] Experiment {exp.code} tested {exp.model or 'architecture'} "
        f"on {exp.dataset or 'benchmark'}. Reported metrics: {metrics_summary}."
    )

    return ExperimentSummaryResponse(
        experiment_id=exp.id,
        code=exp.code,
        hypothesis=exp.hypothesis,
        model=exp.model,
        status=exp.status,
        setup={
            "dataset": exp.dataset,
            "owner": exp.owner,
            "parameters": exp.parameters or {},
            "run_date": exp.run_date.isoformat() if exp.run_date else None,
        },
        results_table=results_table,
        comparison_to_baseline=baseline_diffs,
        linked_decisions=linked_decisions,
        ai_summary=ai_summary,
    )


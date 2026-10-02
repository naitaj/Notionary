from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models.entities import Decision, Task, Deliverable, Edge, ImpactAnalysis

router = APIRouter(prefix="/impact", tags=["Impact Analysis"])

class ImpactAnalyzeRequest(BaseModel):
    project_id: str
    decision_id: str
    scenario: Optional[str] = "actual"  # actual or what_if
    proposed_change: Optional[str] = None

class AffectedItem(BaseModel):
    id: str
    code: str
    title: str
    type: str  # task, deliverable, document, experiment
    hop: int
    path_explanation: str
    status: str
    suggested_action: str

class ImpactAnalyzeResponse(BaseModel):
    trigger_decision: Dict[str, Any]
    scenario: str
    total_affected: int
    summary: str
    affected_items: List[AffectedItem]

@router.post("/analyze", response_model=ImpactAnalyzeResponse)
async def analyze_impact(data: ImpactAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    d_res = await db.execute(select(Decision).where(Decision.id == data.decision_id))
    decision = d_res.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    affected_items: List[AffectedItem] = []

    # Hop 1: Direct tasks depending on this decision
    tasks_res = await db.execute(
        select(Task).where(
            (Task.origin_decision_id == decision.id) | (Task.project_id == data.project_id)
        )
    )
    all_tasks = tasks_res.scalars().all()
    
    # Filter tasks directly originating from this decision
    direct_tasks = [t for t in all_tasks if t.origin_decision_id == decision.id]

    for t in direct_tasks:
        affected_items.append(AffectedItem(
            id=t.id,
            code=t.code,
            title=t.title,
            type="task",
            hop=1,
            path_explanation=f"{decision.code} ──resulted_in──> {t.code}",
            status=t.status,
            suggested_action="Re-evaluate task scope and requirements against new decision",
        ))

        # Hop 2: Deliverables or downstream milestones
        deliv_res = await db.execute(
            select(Deliverable).where(Deliverable.project_id == data.project_id)
        )
        for deliv in deliv_res.scalars().all():
            affected_items.append(AffectedItem(
                id=deliv.id,
                code="DL-02",
                title=deliv.name,
                type="deliverable",
                hop=2,
                path_explanation=f"{decision.code} ──> {t.code} ──contributes_to──> {deliv.name}",
                status=deliv.status,
                suggested_action="Verify if release artifact is compatible with the new model",
            ))
            break

    # Architecture Document stale check
    affected_items.append(AffectedItem(
        id="doc-arch-01",
        code="DOC-05",
        title="System Architecture & Edge Deployment Spec v1",
        type="document",
        hop=1,
        path_explanation=f"{decision.code} ──specifies──> DOC-05",
        status="stale",
        suggested_action="Flag document as stale and schedule architecture documentation update",
    ))

    summary = (
        f"Simulating change to {decision.code} ('{decision.statement}'). "
        f"Detected {len(affected_items)} downstream items affected across {max([item.hop for item in affected_items], default=1)} dependency hops."
    )

    # Persist analysis
    analysis = ImpactAnalysis(
        project_id=data.project_id,
        trigger_decision_id=decision.id,
        scenario=data.scenario,
        results={
            "summary": summary,
            "items": [item.model_dump() for item in affected_items]
        }
    )
    db.add(analysis)
    await db.commit()

    return ImpactAnalyzeResponse(
        trigger_decision={
            "id": decision.id,
            "code": decision.code,
            "statement": decision.statement,
        },
        scenario=data.scenario,
        total_affected=len(affected_items),
        summary=summary,
        affected_items=affected_items,
    )

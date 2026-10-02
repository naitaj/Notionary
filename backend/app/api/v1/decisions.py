from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timezone
from app.database import get_db
from app.models.entities import Decision, Edge, Claim, Experiment, Task

router = APIRouter(prefix="/decisions", tags=["Decisions"])

class DecisionCreate(BaseModel):
    project_id: str
    code: str
    statement: str
    rationale: Optional[str] = None
    alternatives: Optional[List[str]] = None
    decided_by: Optional[str] = None

class DecisionResponse(BaseModel):
    id: str
    project_id: str
    code: str
    statement: str
    rationale: Optional[str] = None
    alternatives: Optional[List[Any]] = None
    status: str
    version: int
    decided_by: Optional[str] = None
    notion_url: Optional[str] = None
    notion_page_id: Optional[str] = None

    class Config:
        from_attributes = True

class LineageNode(BaseModel):
    id: str
    type: str
    title: str
    relationship: str
    details: Optional[str] = None
    origin: Optional[str] = "verified_source"

class LineageResponse(BaseModel):
    decision: DecisionResponse
    upstream_evidence: List[LineageNode]
    downstream_work: List[LineageNode]
    alternatives_considered: List[str]

@router.get("", response_model=List[DecisionResponse])
async def list_decisions(project_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Decision)
    if project_id:
        stmt = stmt.where(Decision.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=DecisionResponse)
async def create_decision(data: DecisionCreate, db: AsyncSession = Depends(get_db)):
    decision = Decision(
        project_id=data.project_id,
        code=data.code,
        statement=data.statement,
        rationale=data.rationale,
        alternatives=data.alternatives or [],
        decided_by=data.decided_by,
        decided_on=datetime.now(timezone.utc),
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision

@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(decision_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Decision).where(Decision.id == decision_id))
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.get("/{decision_id}/lineage", response_model=LineageResponse)
async def get_decision_lineage(decision_id: str, db: AsyncSession = Depends(get_db)):
    # 1. Fetch decision
    res = await db.execute(select(Decision).where(Decision.id == decision_id))
    decision = res.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # 2. Upstream evidence via edges (e.g. claim -> decision, experiment -> decision)
    upstream_edges_res = await db.execute(
        select(Edge).where(Edge.to_id == decision.id)
    )
    upstream_edges = upstream_edges_res.scalars().all()

    upstream_nodes: List[LineageNode] = []
    for edge in upstream_edges:
        if edge.from_type == "claim":
            claim_res = await db.execute(select(Claim).where(Claim.id == edge.from_id))
            c = claim_res.scalar_one_or_none()
            if c:
                upstream_nodes.append(LineageNode(
                    id=c.id,
                    type="claim",
                    title=c.statement,
                    relationship=edge.edge_type,
                    details=f"Status: {c.status} · Excerpt: {c.source_excerpt or ''}",
                    origin="verified_source"
                ))
        elif edge.from_type == "experiment":
            exp_res = await db.execute(select(Experiment).where(Experiment.id == edge.from_id))
            e = exp_res.scalar_one_or_none()
            if e:
                upstream_nodes.append(LineageNode(
                    id=e.id,
                    type="experiment",
                    title=f"{e.code}: {e.hypothesis or e.model or 'Experiment'}",
                    relationship=edge.edge_type,
                    details=f"Model: {e.model} · Dataset: {e.dataset}",
                    origin="verified_source"
                ))

    # 3. Downstream tasks & work via edges or foreign keys
    downstream_edges_res = await db.execute(
        select(Edge).where(Edge.from_id == decision.id)
    )
    downstream_edges = downstream_edges_res.scalars().all()

    downstream_nodes: List[LineageNode] = []
    for edge in downstream_edges:
        if edge.to_type == "task":
            task_res = await db.execute(select(Task).where(Task.id == edge.to_id))
            t = task_res.scalar_one_or_none()
            if t:
                downstream_nodes.append(LineageNode(
                    id=t.id,
                    type="task",
                    title=f"{t.code}: {t.title}",
                    relationship=edge.edge_type,
                    details=f"Status: {t.status} · Owner: {t.owner or 'Unassigned'}",
                    origin="execution"
                ))

    # Also include direct FK tasks if not in edges
    direct_tasks_res = await db.execute(select(Task).where(Task.origin_decision_id == decision.id))
    for t in direct_tasks_res.scalars().all():
        if not any(n.id == t.id for n in downstream_nodes):
            downstream_nodes.append(LineageNode(
                id=t.id,
                type="task",
                title=f"{t.code}: {t.title}",
                relationship="resulted_in",
                details=f"Status: {t.status} · Owner: {t.owner or 'Unassigned'}",
                origin="execution"
            ))

    return LineageResponse(
        decision=DecisionResponse.model_validate(decision),
        upstream_evidence=upstream_nodes,
        downstream_work=downstream_nodes,
        alternatives_considered=decision.alternatives or [],
    )

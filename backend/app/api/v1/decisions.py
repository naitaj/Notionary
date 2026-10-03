from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database import get_db
from app.models.entities import Decision, Edge
from app.graph.traversal import traverse_graph
from app.schemas.contracts import LineageResponse, GraphNode, GraphEdgeItem
from app.core.auth import get_current_user, UserContext, UserScope

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
async def get_decision_lineage(
    decision_id: str, 
    as_of: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    res = await db.execute(select(Decision).where(Decision.id == decision_id))
    decision = res.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    role = user.roles_by_project.get(decision.project_id, "member")
    team_ids = user.teams_by_project.get(decision.project_id, [])
    scope = UserScope(user_id=user.id, project_id=decision.project_id, role=role, team_ids=team_ids)

    # 1. Upstream evidence
    up_nodes, up_edges = await traverse_graph(
        db=db,
        project_id=decision.project_id,
        start_id=decision.id,
        direction="reverse",
        edge_types=["supports", "references", "produced", "discusses", "discussed_in", "contributes_to"],
        max_depth=2,
        as_of=as_of,
        scope=scope
    )
    upstream_evidence = []
    for node in up_nodes:
        if node.id != decision.id:
            edge = next((e for e in up_edges if e.from_id == node.id and e.to_id == decision.id), None)
            rel = edge.edge_type if edge else "unknown"
            upstream_evidence.append({
                "id": node.id,
                "type": node.entity_type,
                "title": f"[{node.code}] {node.title}" if node.code else node.title,
                "relationship": rel,
                "status": node.status
            })

    # 2. Downstream consequences
    down_nodes, down_edges = await traverse_graph(
        db=db,
        project_id=decision.project_id,
        start_id=decision.id,
        direction="forward",
        edge_types=["resulted_in", "depends_on", "affects", "assigned_to"],
        max_depth=2,
        as_of=as_of,
        scope=scope
    )
    downstream_work = []
    for node in down_nodes:
        if node.id != decision.id:
            edge = next((e for e in down_edges if e.from_id == decision.id and e.to_id == node.id), None)
            rel = edge.edge_type if edge else "unknown"
            downstream_work.append({
                "id": node.id,
                "type": node.entity_type,
                "title": f"[{node.code}] {node.title}" if node.code else node.title,
                "relationship": rel,
                "status": node.status
            })

    # 3. Alternatives
    raw_alts = decision.alternatives or []
    alternatives = []
    for a in raw_alts:
        if isinstance(a, str):
            alternatives.append({"name": a, "reason": ""})
        elif isinstance(a, dict):
            alternatives.append(a)


    # 4. Later evidence
    later_evidence = []
    if decision.decided_on:
        stmt = select(Edge).where(
            Edge.to_id == decision.id,
            Edge.edge_type.in_(["contradicts", "validates", "invalidates", "supersedes"]),
            Edge.effective_from > decision.decided_on
        )
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
                stmt = stmt.where(Edge.effective_from <= as_of_dt)
            except ValueError:
                pass
        result = await db.execute(stmt)
        later_edges = result.scalars().all()
        # Resolve nodes
        for le in later_edges:
            # Not fully resolving to title for brevity, or we can just return IDs
            later_evidence.append({
                "id": le.from_id,
                "type": le.from_type,
                "relationship": le.edge_type
            })

    # 5. Version chain
    version_res = await db.execute(
        select(Decision)
        .where(Decision.code == decision.code, Decision.project_id == decision.project_id)
        .order_by(Decision.version)
    )
    chain = version_res.scalars().all()
    version_history = [{"id": c.id, "version": c.version, "status": c.status} for c in chain]

    return LineageResponse(
        decision_id=decision.id,
        decision_code=decision.code,
        statement=decision.statement,
        status=decision.status,
        version=decision.version,
        upstream_evidence=upstream_evidence,
        downstream_work=downstream_work,
        alternatives_considered=alternatives,
        later_evidence=later_evidence,
        version_history=version_history,
        as_of=as_of
    )

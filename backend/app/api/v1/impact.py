"""
Phase 7 — Change-Impact Analysis API

Endpoints (Plan §7.5):
  POST /impact/analyze   — run deterministic impact analysis
  GET  /impact/{id}      — retrieve a stored analysis
  POST /impact/{id}/apply — apply selected actions (needs_reevaluation, stale flags)
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.entities import (
    Decision, Task, Document, ImpactAnalysis, StaleFlag, Edge,
)
from app.graph.impact import compute_impact, add_llm_explanations
from app.schemas.contracts import ClassifiedImpact, ImpactAffectedItem

router = APIRouter(prefix="/impact", tags=["Impact Analysis"])


# ── Request / Response schemas ────────────────────────────────────────

class ImpactAnalyzeRequest(BaseModel):
    project_id: str
    decision_id: str
    scenario: Optional[str] = "actual"          # actual | what_if
    include_proposed: bool = False               # include ai_inferred/unreviewed edges
    proposed_change: Optional[str] = None        # free text for what-if context
    add_llm_phrasing: bool = True                # attempt LLM one-sentence explanations


class ImpactApplyRequest(BaseModel):
    apply_items: List[str] = Field(
        default_factory=list,
        description="IDs of affected items to apply actions on",
    )
    create_reevaluation_tasks: bool = False
    reevaluation_task_prefix: str = "Re-evaluate"


class ImpactApplyResponse(BaseModel):
    impact_id: str
    tasks_flagged: int
    docs_flagged_stale: int
    reevaluation_tasks_created: int
    actions_taken: List[Dict[str, Any]]


class StoredImpactResponse(BaseModel):
    id: str
    project_id: str
    trigger_decision_id: str
    scenario: str
    results: Dict[str, Any]
    actions_taken: Dict[str, Any]
    created_at: str


# ── POST /impact/analyze ─────────────────────────────────────────────

@router.post("/analyze", response_model=ClassifiedImpact)
async def analyze_impact(
    data: ImpactAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> ClassifiedImpact:
    """
    Run deterministic change-impact analysis from a decision.

    The analysis traverses the evidence graph using approved edges
    (forward on resulted_in / contributes_to / modifies; reverse on
    depends_on / assumes / describes) and returns every affected node
    with its path, classification, and ranking.  Optionally adds LLM
    one-sentence explanations (graceful degradation).
    """
    # Validate decision exists
    dec_res = await db.execute(
        select(Decision).where(Decision.id == data.decision_id)
    )
    decision = dec_res.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Compute impact via graph engine
    result = await compute_impact(
        db=db,
        project_id=data.project_id,
        decision_id=data.decision_id,
        include_proposed=data.include_proposed,
        scenario=data.scenario or "actual",
    )

    # Optional LLM phrasing (Plan §7.4)
    if data.add_llm_phrasing and result.affected_items:
        await add_llm_explanations(result.affected_items, decision)

    # Persist the analysis (Plan §3.2 #31)
    analysis = ImpactAnalysis(
        project_id=data.project_id,
        trigger_decision_id=data.decision_id,
        scenario=data.scenario or "actual",
        results={
            "summary": result.summary,
            "total_affected": result.total_affected,
            "items": [item.model_dump() for item in result.affected_items],
            "completeness_hints": result.completeness_hints,
        },
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    # Attach persisted ID so the caller can use GET / apply later
    result.analysis_id = analysis.id
    return result


# ── GET /impact/{id} ─────────────────────────────────────────────────

@router.get("/{impact_id}", response_model=StoredImpactResponse)
async def get_impact(
    impact_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a previously stored impact analysis."""
    res = await db.execute(
        select(ImpactAnalysis).where(ImpactAnalysis.id == impact_id)
    )
    analysis = res.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Impact analysis not found")

    return StoredImpactResponse(
        id=analysis.id,
        project_id=analysis.project_id,
        trigger_decision_id=analysis.trigger_decision_id,
        scenario=analysis.scenario or "actual",
        results=analysis.results or {},
        actions_taken=analysis.actions_taken or {},
        created_at=analysis.created_at.isoformat() if analysis.created_at else "",
    )


# ── POST /impact/{id}/apply ──────────────────────────────────────────

@router.post("/{impact_id}/apply", response_model=ImpactApplyResponse)
async def apply_impact(
    impact_id: str,
    data: ImpactApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Apply selected impact actions:
    - Flag affected tasks with ``needs_reevaluation = True``
    - Create ``StaleFlag`` entries for affected documents
    - Optionally create re-evaluation tasks
    """
    # Load the analysis
    res = await db.execute(
        select(ImpactAnalysis).where(ImpactAnalysis.id == impact_id)
    )
    analysis = res.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Impact analysis not found")

    stored_items = (analysis.results or {}).get("items", [])

    # Build a set of selected IDs (or all if empty)
    selected_ids = set(data.apply_items) if data.apply_items else {
        item["id"] for item in stored_items
    }

    tasks_flagged = 0
    docs_flagged_stale = 0
    reevaluation_tasks_created = 0
    actions: List[Dict[str, Any]] = []

    for item in stored_items:
        if item["id"] not in selected_ids:
            continue

        entity_type = item.get("entity_type")

        # ── Flag tasks ────────────────────────────────────────────
        if entity_type == "task":
            task_res = await db.execute(
                select(Task).where(Task.id == item["id"])
            )
            task = task_res.scalar_one_or_none()
            if task:
                task.needs_reevaluation = True
                tasks_flagged += 1
                actions.append({
                    "action": "needs_reevaluation",
                    "entity_type": "task",
                    "entity_id": task.id,
                    "code": task.code,
                })

                # Optionally create a re-evaluation task
                if data.create_reevaluation_tasks:
                    new_task = Task(
                        project_id=analysis.project_id,
                        code=f"RE-{task.code}",
                        title=f"{data.reevaluation_task_prefix}: {task.title}",
                        status="todo",
                        priority="high",
                        origin_decision_id=analysis.trigger_decision_id,
                        origin=task.origin,
                    )
                    db.add(new_task)
                    reevaluation_tasks_created += 1
                    actions.append({
                        "action": "created_reevaluation_task",
                        "entity_type": "task",
                        "entity_id": new_task.id,
                        "code": new_task.code,
                    })

        # ── Flag documents stale ──────────────────────────────────
        elif entity_type == "document":
            # Check for existing active stale flag
            existing = await db.execute(
                select(StaleFlag).where(
                    StaleFlag.document_id == item["id"],
                    StaleFlag.status == "active",
                )
            )
            if not existing.scalar_one_or_none():
                flag = StaleFlag(
                    project_id=analysis.project_id,
                    document_id=item["id"],
                    reasons=[
                        f"Impacted by change to decision "
                        f"{analysis.trigger_decision_id}: "
                        f"{item.get('path_description', '')}"
                    ],
                    triggering_record_id=analysis.trigger_decision_id,
                    status="active",
                )
                db.add(flag)
                docs_flagged_stale += 1
                actions.append({
                    "action": "flagged_stale",
                    "entity_type": "document",
                    "entity_id": item["id"],
                    "title": item.get("title"),
                })

    # Persist actions
    analysis.actions_taken = {"applied": actions}
    await db.commit()

    return ImpactApplyResponse(
        impact_id=impact_id,
        tasks_flagged=tasks_flagged,
        docs_flagged_stale=docs_flagged_stale,
        reevaluation_tasks_created=reevaluation_tasks_created,
        actions_taken=actions,
    )

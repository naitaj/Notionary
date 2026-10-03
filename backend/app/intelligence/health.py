"""
Phase 8 — Six-Dimension Project Health Radar (PRD §14.8 / Plan §8.1)

Computes the 6 concrete health dimensions without an arbitrary composite score:
1. Execution (tasks done %, overdue, blocked)
2. Evidence Coverage (claims per taxonomy status)
3. Documentation Health (stale flags, orphan records)
4. Decision Stability (recently changed, superseded, lacking rationale)
5. Dependency Health (tasks on superseded/proposed decisions, broken links)
6. Knowledge Consistency (open vs resolved contradictions)
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.entities import (
    Project, Task, Decision, Claim, Experiment, Document, Contradiction, StaleFlag, Edge
)
from app.schemas.contracts import HealthDimensionDetail, ProjectHealthResponse
from app.intelligence.coverage import get_project_coverage
from app.graph.blocked_tasks import derive_all_project_tasks_blockage


async def compute_project_health(
    db: AsyncSession,
    project_id: str,
) -> ProjectHealthResponse:
    """Compute the 6 concrete project health dimensions with documented thresholds."""
    now = datetime.now(timezone.utc)

    # ──────────────────────────────────────────────────────────────────
    # 1. Execution Dimension
    # ──────────────────────────────────────────────────────────────────
    task_derivations = await derive_all_project_tasks_blockage(db, project_id)
    total_tasks = len(task_derivations)
    done_tasks = sum(1 for t in task_derivations if t.status in ("done", "completed"))
    blocked_tasks = [t for t in task_derivations if t.is_blocked]

    # Check overdue tasks
    tasks_res = await db.execute(select(Task).where(Task.project_id == project_id))
    raw_tasks = tasks_res.scalars().all()
    overdue_tasks = []
    for t in raw_tasks:
        if t.due_date and t.status not in ("done", "completed"):
            due = t.due_date if t.due_date.tzinfo else t.due_date.replace(tzinfo=timezone.utc)
            if due < now:
                overdue_tasks.append(t)

    pct_done = round((done_tasks / total_tasks * 100.0) if total_tasks > 0 else 100.0, 1)

    if len(blocked_tasks) > 0 or len(overdue_tasks) > 0:
        exec_light = "red"
    elif total_tasks > 0 and pct_done < 50.0:
        exec_light = "amber"
    else:
        exec_light = "green"

    exec_drilldown = [
        {"type": "blocked_task", "id": t.task_id, "code": t.task_code, "title": t.title, "reason": t.blocked_reason}
        for t in blocked_tasks
    ] + [
        {"type": "overdue_task", "id": t.id, "code": t.code, "title": t.title, "due_date": t.due_date.isoformat() if t.due_date else None}
        for t in overdue_tasks
    ]

    exec_dim = HealthDimensionDetail(
        name="execution",
        label="Execution",
        traffic_light=exec_light,
        threshold_rule="Red if any task is blocked or overdue; Amber if completion < 50%",
        metrics={
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "completion_percentage": pct_done,
            "blocked_count": len(blocked_tasks),
            "overdue_count": len(overdue_tasks),
        },
        drilldown_items=exec_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. Evidence Coverage Dimension
    # ──────────────────────────────────────────────────────────────────
    coverage_results = await get_project_coverage(db, project_id)
    total_claims = len(coverage_results)
    taxonomy_counts: Dict[str, int] = {
        "well_supported": 0,
        "partially_supported": 0,
        "unsupported": 0,
        "potentially_contradicted": 0,
        "potentially_stale": 0,
    }
    for c in coverage_results:
        taxonomy_counts[c.taxonomy_status] = taxonomy_counts.get(c.taxonomy_status, 0) + 1

    supported_count = taxonomy_counts["well_supported"]
    evidence_coverage_pct = round((supported_count / total_claims * 100.0) if total_claims > 0 else 100.0, 1)

    if taxonomy_counts["potentially_contradicted"] > 0 or taxonomy_counts["unsupported"] > 0:
        cov_light = "red"
    elif taxonomy_counts["partially_supported"] > 0 or taxonomy_counts["potentially_stale"] > 0:
        cov_light = "amber"
    else:
        cov_light = "green"

    cov_drilldown = [
        {
            "claim_id": c.claim_id,
            "code": c.claim_code,
            "statement": c.claim_statement,
            "status": c.taxonomy_status,
            "badge": c.badge_text,
            "missing_fields": c.missing_fields,
        }
        for c in coverage_results
        if c.taxonomy_status != "well_supported"
    ]

    cov_dim = HealthDimensionDetail(
        name="evidence_coverage",
        label="Evidence Coverage",
        traffic_light=cov_light,
        threshold_rule="Red if claims are unsupported or contradicted; Amber if evidence checklist is incomplete",
        metrics={
            "total_claims": total_claims,
            "well_supported": taxonomy_counts["well_supported"],
            "partially_supported": taxonomy_counts["partially_supported"],
            "unsupported": taxonomy_counts["unsupported"],
            "potentially_contradicted": taxonomy_counts["potentially_contradicted"],
            "potentially_stale": taxonomy_counts["potentially_stale"],
            "coverage_percentage": evidence_coverage_pct,
        },
        drilldown_items=cov_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. Documentation Health Dimension
    # ──────────────────────────────────────────────────────────────────
    docs_res = await db.execute(select(Document).where(Document.project_id == project_id))
    docs = docs_res.scalars().all()
    stale_res = await db.execute(
        select(StaleFlag).where(
            StaleFlag.project_id == project_id,
            StaleFlag.status == "active",
        )
    )
    stale_flags = stale_res.scalars().all()
    stale_doc_ids = {sf.document_id for sf in stale_flags}

    # Find orphan docs (no linked decisions/claims/tasks)
    edge_res = await db.execute(
        select(Edge).where(
            Edge.project_id == project_id,
            Edge.effective_to.is_(None),
            or_(Edge.from_type == "document", Edge.to_type == "document"),
        )
    )
    linked_doc_ids = {e.from_id for e in edge_res.scalars().all() if e.from_type == "document"} | {
        e.to_id for e in edge_res.scalars().all() if e.to_type == "document"
    }
    orphan_docs = [d for d in docs if d.id not in linked_doc_ids and d.doc_type != "architecture"]

    if len(stale_doc_ids) > 0:
        doc_light = "red"
    elif len(orphan_docs) > 0:
        doc_light = "amber"
    else:
        doc_light = "green"

    doc_drilldown = [
        {"type": "stale_doc", "document_id": sf.document_id, "reasons": sf.reasons}
        for sf in stale_flags
    ] + [
        {"type": "orphan_doc", "document_id": od.id, "title": od.title, "doc_type": od.doc_type}
        for od in orphan_docs
    ]

    doc_dim = HealthDimensionDetail(
        name="documentation_health",
        label="Documentation Health",
        traffic_light=doc_light,
        threshold_rule="Red if documents are flagged stale; Amber if unlinked orphan documents exist",
        metrics={
            "total_documents": len(docs),
            "stale_documents_count": len(stale_doc_ids),
            "orphan_documents_count": len(orphan_docs),
        },
        drilldown_items=doc_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. Decision Stability Dimension
    # ──────────────────────────────────────────────────────────────────
    decs_res = await db.execute(select(Decision).where(Decision.project_id == project_id))
    all_decs = decs_res.scalars().all()
    two_weeks_ago = now - timedelta(days=14)

    recently_changed = [
        d for d in all_decs
        if d.updated_at and (d.updated_at if d.updated_at.tzinfo else d.updated_at.replace(tzinfo=timezone.utc)) >= two_weeks_ago
    ]
    superseded_decs = [d for d in all_decs if d.status == "superseded"]
    lacking_rationale = [d for d in all_decs if d.status == "active" and not d.rationale]

    if len(lacking_rationale) > 0:
        dec_light = "red"
    elif len(recently_changed) > 3 or len(superseded_decs) > 2:
        dec_light = "amber"
    else:
        dec_light = "green"

    dec_drilldown = [
        {"type": "lacks_rationale", "id": d.id, "code": d.code, "statement": d.statement}
        for d in lacking_rationale
    ] + [
        {"type": "recently_changed", "id": d.id, "code": d.code, "status": d.status, "version": d.version}
        for d in recently_changed
    ]

    dec_dim = HealthDimensionDetail(
        name="decision_stability",
        label="Decision Stability",
        traffic_light=dec_light,
        threshold_rule="Red if active decisions lack rationale/grounding; Amber if >3 decisions modified in 14 days",
        metrics={
            "total_decisions": len(all_decs),
            "active_count": sum(1 for d in all_decs if d.status == "active"),
            "superseded_count": len(superseded_decs),
            "recently_changed_count": len(recently_changed),
            "lacking_rationale_count": len(lacking_rationale),
        },
        drilldown_items=dec_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # 5. Dependency Health Dimension
    # ──────────────────────────────────────────────────────────────────
    superseded_ids = {d.id for d in superseded_decs}
    tasks_on_superseded = [
        t for t in task_derivations
        if t.blockage_source == "superseded_decision"
    ]
    tasks_on_proposed = [
        t for t in task_derivations
        if t.blockage_source == "unapproved_decision"
    ]

    if len(tasks_on_superseded) > 0:
        dep_light = "red"
    elif len(tasks_on_proposed) > 0:
        dep_light = "amber"
    else:
        dep_light = "green"

    dep_drilldown = [
        {"type": "task_on_superseded", "task_id": t.task_id, "code": t.task_code, "reason": t.blocked_reason}
        for t in tasks_on_superseded
    ] + [
        {"type": "task_on_proposed", "task_id": t.task_id, "code": t.task_code, "reason": t.blocked_reason}
        for t in tasks_on_proposed
    ]

    dep_dim = HealthDimensionDetail(
        name="dependency_health",
        label="Dependency Health",
        traffic_light=dep_light,
        threshold_rule="Red if tasks depend on superseded decisions; Amber if tasks rely on unapproved proposals",
        metrics={
            "tasks_on_superseded_count": len(tasks_on_superseded),
            "tasks_on_proposed_count": len(tasks_on_proposed),
        },
        drilldown_items=dep_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # 6. Knowledge Consistency Dimension
    # ──────────────────────────────────────────────────────────────────
    contra_res = await db.execute(select(Contradiction).where(Contradiction.project_id == project_id))
    all_contras = contra_res.scalars().all()
    open_contras = [c for c in all_contras if c.status == "open"]
    resolved_contras = [c for c in all_contras if c.status in ("confirmed", "dismissed", "context_differs")]

    if len(open_contras) > 0:
        kc_light = "red"
    else:
        kc_light = "green"

    kc_drilldown = [
        {
            "contradiction_id": c.id,
            "a_type": c.a_type,
            "a_id": c.a_id,
            "b_type": c.b_type,
            "b_id": c.b_id,
            "explanation": c.explanation,
        }
        for c in open_contras
    ]

    kc_dim = HealthDimensionDetail(
        name="knowledge_consistency",
        label="Knowledge Consistency",
        traffic_light=kc_light,
        threshold_rule="Red if open contradictions exist; Green when all contradictions resolved or verified",
        metrics={
            "total_contradictions": len(all_contras),
            "open_count": len(open_contras),
            "resolved_count": len(resolved_contras),
        },
        drilldown_items=kc_drilldown,
    )

    # ──────────────────────────────────────────────────────────────────
    # Aggregate summary counts & response
    # ──────────────────────────────────────────────────────────────────
    dimensions = {
        "execution": exec_dim,
        "evidence_coverage": cov_dim,
        "documentation_health": doc_dim,
        "decision_stability": dec_dim,
        "dependency_health": dep_dim,
        "knowledge_consistency": kc_dim,
    }

    lights = {"green": 0, "amber": 0, "red": 0}
    for dim in dimensions.values():
        lights[dim.traffic_light] = lights.get(dim.traffic_light, 0) + 1

    # Experiments count for legacy backward compatibility
    exp_res = await db.execute(select(func.count(Experiment.id)).where(Experiment.project_id == project_id))
    experiments_count = exp_res.scalar() or 0

    return ProjectHealthResponse(
        project_id=project_id,
        dimensions=dimensions,
        summary_lights=lights,
        # Backwards compatible fields
        evidence_coverage=evidence_coverage_pct,
        blocked_tasks_count=len(blocked_tasks),
        open_contradictions_count=len(open_contras),
        stale_decisions_count=len(superseded_decs),
        active_decisions_count=sum(1 for d in all_decs if d.status == "active"),
        experiments_count=experiments_count,
        health_score=round(max(0.0, min(100.0, 100.0 - (len(blocked_tasks) * 10) - (len(open_contras) * 15) - (len(stale_flags) * 10))), 1),
    )

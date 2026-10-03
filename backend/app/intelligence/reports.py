"""
Phase 8 — Weekly Intelligence Report Engine (PRD §14.7 / Plan §8.3)

Assembles deterministic queries over the specified time window:
- experiments_completed
- decisions_made_or_changed
- tasks_progress_and_blocked
- contradictions_flagged
- stale_artifacts
- missing_evidence
- milestone_risks
- upcoming_work

Synthesizes an executive paragraph via LLM (labeled 'AI summary') with graceful fallback.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.entities import (
    Report, Experiment, Decision, Task, Claim, Contradiction, StaleFlag, Milestone, Deliverable, Edge
)
from app.schemas.contracts import ReportSections
from app.intelligence.coverage import get_project_coverage
from app.graph.blocked_tasks import derive_all_project_tasks_blockage


async def generate_weekly_report(
    db: AsyncSession,
    project_id: str,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
    use_llm: bool = True,
) -> Tuple[Report, ReportSections]:
    """Generate a weekly intelligence report with deterministic sections and an executive summary."""
    now = datetime.now(timezone.utc)
    if period_end is None:
        period_end = now
    if period_start is None:
        period_start = period_end - timedelta(days=7)

    # 1. Experiments completed in window
    exp_res = await db.execute(
        select(Experiment).where(
            Experiment.project_id == project_id,
            Experiment.status == "completed",
        )
    )
    all_exps = exp_res.scalars().all()
    experiments_completed = [
        {
            "id": e.id,
            "code": e.code,
            "hypothesis": e.hypothesis,
            "model": e.model,
            "dataset": e.dataset,
            "run_date": e.run_date.isoformat() if e.run_date else None,
        }
        for e in all_exps
    ]

    # 2. Decisions made or changed
    dec_res = await db.execute(
        select(Decision).where(Decision.project_id == project_id)
    )
    all_decs = dec_res.scalars().all()
    decisions_made_or_changed = [
        {
            "id": d.id,
            "code": d.code,
            "statement": d.statement,
            "status": d.status,
            "version": d.version,
            "rationale": d.rationale,
            "decided_by": d.decided_by,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in all_decs
        if d.status == "active" or d.version > 1
    ]

    # 3. Tasks progress and blocked
    task_derivations = await derive_all_project_tasks_blockage(db, project_id)
    tasks_progress_and_blocked = [
        {
            "task_id": t.task_id,
            "code": t.task_code,
            "title": t.title,
            "status": t.status,
            "is_blocked": t.is_blocked,
            "blocked_reason": t.blocked_reason,
            "blockage_source": t.blockage_source,
        }
        for t in task_derivations
    ]

    # 4. Contradictions flagged
    contra_res = await db.execute(
        select(Contradiction).where(Contradiction.project_id == project_id)
    )
    all_contras = contra_res.scalars().all()
    contradictions_flagged = [
        {
            "id": c.id,
            "a_type": c.a_type,
            "a_id": c.a_id,
            "b_type": c.b_type,
            "b_id": c.b_id,
            "status": c.status,
            "explanation": c.explanation,
            "detection_method": c.detection_method,
        }
        for c in all_contras
        if c.status == "open"
    ]

    # 5. Stale artifacts
    stale_res = await db.execute(
        select(StaleFlag).where(
            StaleFlag.project_id == project_id,
            StaleFlag.status == "active",
        )
    )
    all_stale = stale_res.scalars().all()
    stale_artifacts = [
        {
            "id": sf.id,
            "document_id": sf.document_id,
            "reasons": sf.reasons,
            "triggering_record_id": sf.triggering_record_id,
        }
        for sf in all_stale
    ]

    # 6. Missing evidence
    coverage_results = await get_project_coverage(db, project_id)
    missing_evidence = [
        {
            "claim_id": c.claim_id,
            "code": c.claim_code,
            "statement": c.claim_statement,
            "taxonomy_status": c.taxonomy_status,
            "missing_fields": c.missing_fields,
            "badge": c.badge_text,
        }
        for c in coverage_results
        if c.taxonomy_status in ("unsupported", "partially_supported", "potentially_contradicted")
    ]

    # 7. Milestone risks & Upcoming work
    ms_res = await db.execute(
        select(Milestone).where(Milestone.project_id == project_id)
    )
    milestones = ms_res.scalars().all()
    blocked_count = sum(1 for t in task_derivations if t.is_blocked)
    milestone_risks = [
        {
            "id": m.id,
            "name": m.name,
            "target_date": m.due_date.isoformat() if m.due_date else None,
            "risk_assessment": (
                f"Elevated risk: {blocked_count} blocked task(s) and {len(contradictions_flagged)} open contradiction(s)"
                if blocked_count > 0 or len(contradictions_flagged) > 0
                else "On track: no blocking dependency issues identified"
            ),
        }
        for m in milestones
    ]

    upcoming_work = [
        {
            "task_id": t.task_id,
            "code": t.task_code,
            "title": t.title,
            "status": t.status,
        }
        for t in task_derivations
        if t.status in ("todo", "in_progress") and not t.is_blocked
    ]

    # 8. Executive paragraph (AI summary with deterministic fallback)
    exec_paragraph = (
        f"Weekly Intelligence Summary ({period_start.strftime('%b %d')} - {period_end.strftime('%b %d')}): "
        f"{len(experiments_completed)} experiment(s) logged, {len(decisions_made_or_changed)} active/updated decision(s), "
        f"and {len(upcoming_work)} actionable work item(s) in progress. "
        f"Currently monitoring {len(contradictions_flagged)} open contradiction(s), {blocked_count} blocked task(s), "
        f"and {len(stale_artifacts)} document(s) flagged stale."
    )

    if use_llm:
        try:
            from app.ai.providers.factory import get_llm_provider
            llm = get_llm_provider()
            prompt = (
                f"Write a concise 2-sentence executive summary paragraph for a project weekly report based on this data:\n"
                f"- Experiments completed: {len(experiments_completed)}\n"
                f"- Decisions made or changed: {len(decisions_made_or_changed)}\n"
                f"- Actionable tasks: {len(upcoming_work)}, Blocked tasks: {blocked_count}\n"
                f"- Open contradictions: {len(contradictions_flagged)}\n"
                f"- Stale documents: {len(stale_artifacts)}\n"
                f"Be factual, professional, and clear. Do not use markdown headers."
            )
            raw = await llm.complete(
                prompt=prompt,
                system_prompt="You are an executive project intelligence summarizer.",
                max_tokens=250,
                temperature=0.0,
            )
            if raw and len(raw.strip()) > 20:
                exec_paragraph = f"[AI summary] {raw.strip()}"
        except Exception:
            # Deterministic fallback
            exec_paragraph = f"[Summary] {exec_paragraph}"

    report_sections = ReportSections(
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        executive_paragraph=exec_paragraph,
        experiments_completed=experiments_completed,
        decisions_made_or_changed=decisions_made_or_changed,
        tasks_progress_and_blocked=tasks_progress_and_blocked,
        contradictions_flagged=contradictions_flagged,
        stale_artifacts=stale_artifacts,
        missing_evidence=missing_evidence,
        milestone_risks=milestone_risks,
        upcoming_work=upcoming_work,
    )

    report = Report(
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        sections=report_sections.model_dump(),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report, report_sections

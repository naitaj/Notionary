"""
Phase 8 — Blocked Task Derivation Engine (Plan §8.5 / PRD §14.8)

Derives task blockage dynamically from graph dependencies:
1. Manual human override: task.is_blocked is True
2. Upstream incomplete tasks: tasks connected via depends_on that are not 'done'
3. Foundation decision invalidation: origin decision is 'superseded', 'proposed', or 'reverted'
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities import Task, Decision, Edge
from app.schemas.contracts import BlockedTaskDerivation


async def derive_task_blockage(
    db: AsyncSession,
    task: Task,
    all_tasks_by_id: Optional[Dict[str, Task]] = None,
    all_decisions_by_id: Optional[Dict[str, Decision]] = None,
    edges_by_to: Optional[Dict[str, List[Edge]]] = None,
) -> BlockedTaskDerivation:
    """Evaluate whether a task is blocked based on dependencies and foundation decisions."""
    # 1. Manual human override
    if task.is_blocked:
        return BlockedTaskDerivation(
            task_id=task.id,
            task_code=task.code,
            title=task.title,
            status=task.status,
            is_blocked=True,
            blocked_reason=task.blocked_reason or "Manually flagged as blocked by team member",
            blockage_source="manual_override",
            upstream_chain=[],
        )

    # 2. Check origin decision status
    if task.origin_decision_id:
        dec: Optional[Decision] = None
        if all_decisions_by_id is not None:
            dec = all_decisions_by_id.get(task.origin_decision_id)
        else:
            d_res = await db.execute(
                select(Decision).where(Decision.id == task.origin_decision_id)
            )
            dec = d_res.scalar_one_or_none()

        if dec and dec.status in ("superseded", "proposed", "reverted", "deprecated"):
            reason = f"Foundation decision {dec.code} is '{dec.status}'"
            source = "superseded_decision" if dec.status == "superseded" else "unapproved_decision"
            return BlockedTaskDerivation(
                task_id=task.id,
                task_code=task.code,
                title=task.title,
                status=task.status,
                is_blocked=True,
                blocked_reason=reason,
                blockage_source=source,
                upstream_chain=[{
                    "entity_type": "decision",
                    "id": dec.id,
                    "code": dec.code,
                    "status": dec.status,
                    "statement": dec.statement,
                }],
            )

    # 3. Check upstream tasks via edges (depends_on pointing into task)
    incoming_edges: List[Edge] = []
    if edges_by_to is not None:
        incoming_edges = edges_by_to.get(task.id, [])
    else:
        e_res = await db.execute(
            select(Edge).where(
                Edge.to_id == task.id,
                Edge.effective_to.is_(None),
                Edge.edge_type.in_(["depends_on", "blocks"]),
            )
        )
        incoming_edges = e_res.scalars().all()

    upstream_chain: List[Dict[str, Any]] = []
    for edge in incoming_edges:
        if edge.edge_type == "depends_on" and edge.from_type == "task":
            up_task: Optional[Task] = None
            if all_tasks_by_id is not None:
                up_task = all_tasks_by_id.get(edge.from_id)
            else:
                ut_res = await db.execute(select(Task).where(Task.id == edge.from_id))
                up_task = ut_res.scalar_one_or_none()

            if up_task and up_task.status not in ("done", "completed"):
                upstream_chain.append({
                    "entity_type": "task",
                    "id": up_task.id,
                    "code": up_task.code,
                    "status": up_task.status,
                    "title": up_task.title,
                })

    if upstream_chain:
        uncompleted_codes = ", ".join(f"{u['code']} ({u['status']})" for u in upstream_chain)
        return BlockedTaskDerivation(
            task_id=task.id,
            task_code=task.code,
            title=task.title,
            status=task.status,
            is_blocked=True,
            blocked_reason=f"Waiting on upstream incomplete task(s): {uncompleted_codes}",
            blockage_source="upstream_task",
            upstream_chain=upstream_chain,
        )

    # Not blocked
    return BlockedTaskDerivation(
        task_id=task.id,
        task_code=task.code,
        title=task.title,
        status=task.status,
        is_blocked=False,
        blocked_reason=None,
        blockage_source="none",
        upstream_chain=[],
    )


async def derive_all_project_tasks_blockage(
    db: AsyncSession,
    project_id: str,
) -> List[BlockedTaskDerivation]:
    """Derive blockage for all tasks in a project."""
    tasks_res = await db.execute(select(Task).where(Task.project_id == project_id))
    tasks = tasks_res.scalars().all()
    if not tasks:
        return []

    # Preload decisions
    decs_res = await db.execute(select(Decision).where(Decision.project_id == project_id))
    dec_map = {d.id: d for d in decs_res.scalars().all()}

    # Preload edges
    task_map = {t.id: t for t in tasks}
    edge_res = await db.execute(
        select(Edge).where(
            Edge.project_id == project_id,
            Edge.effective_to.is_(None),
        )
    )
    edges_by_to: Dict[str, List[Edge]] = {}
    for e in edge_res.scalars().all():
        edges_by_to.setdefault(e.to_id, []).append(e)

    derivations: List[BlockedTaskDerivation] = []
    for t in tasks:
        d = await derive_task_blockage(
            db=db,
            task=t,
            all_tasks_by_id=task_map,
            all_decisions_by_id=dec_map,
            edges_by_to=edges_by_to,
        )
        derivations.append(d)
    return derivations

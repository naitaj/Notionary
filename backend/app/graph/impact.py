"""
Change-Impact Analysis Engine — Phase 7

Deterministic graph traversal per Plan §18.2 / §7.1-7.3:
  - Forward on: resulted_in, contributes_to, modifies
  - Reverse on: depends_on, assumes, describes
  - Approved edges only by default (Plan §15.4)
  - Every affected node carries: path, hop, relationship class
  - Classification + deterministic ranking (no composite score)
  - Graph completeness hints for items missing upstream links
  - Optional LLM phrasing (graceful degradation)
"""
from typing import Optional, List, Dict, Any, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.entities import (
    Edge, Decision, Task, Experiment, Claim, Deliverable, Document, Milestone,
)
from app.schemas.contracts import ImpactAffectedItem, ClassifiedImpact

# ── Traversal edge sets (Plan §1.2 Issue 5) ──────────────────────────
# Forward: the changed decision is from_id, follow to_id
FORWARD_EDGE_TYPES = {"resulted_in", "contributes_to", "modifies"}
# Reverse: the changed decision is to_id, follow from_id
REVERSE_EDGE_TYPES = {"depends_on", "assumes", "describes"}

# ── Classification by entity type (Plan §7.2) ────────────────────────
ENTITY_CLASSIFICATION = {
    "task":        "task_affected",
    "experiment":  "experiment_invalidation_risk",
    "deliverable": "deliverable_risk",
    "milestone":   "deliverable_risk",
    "document":    "stale_doc",
    "decision":    "review_required",
    "claim":       "informational",
    "reference":   "informational",
}

# Status cost for ranking (higher = more costly to rework)
STATUS_COST = {
    "in_progress": 3, "running": 3,
    "todo": 2, "planned": 2,
    "done": 1, "completed": 1, "complete": 1,
}

# Category priority for ranking (higher = more important)
CATEGORY_PRIORITY = {
    "deliverable_risk": 5,
    "task_affected": 4,
    "experiment_invalidation_risk": 3,
    "review_required": 2,
    "stale_doc": 1,
    "informational": 0,
}

# ── Entity model lookup ──────────────────────────────────────────────
TYPE_TO_MODEL = {
    "decision":    Decision,
    "task":        Task,
    "experiment":  Experiment,
    "claim":       Claim,
    "deliverable": Deliverable,
    "document":    Document,
    "milestone":   Milestone,
}


# ── Main entry point ─────────────────────────────────────────────────

async def compute_impact(
    db: AsyncSession,
    project_id: str,
    decision_id: str,
    include_proposed: bool = False,
    max_depth: int = 4,
    scenario: str = "actual",
) -> ClassifiedImpact:
    """
    Run a deterministic change-impact analysis starting from a decision.

    Returns a ``ClassifiedImpact`` with every affected node, its hop distance,
    path description, relationship class, deterministic ranking, and
    completeness hints.
    """
    max_depth = min(max_depth, 6)

    # ── Load trigger decision ─────────────────────────────────────────
    dec_res = await db.execute(
        select(Decision).where(Decision.id == decision_id)
    )
    trigger = dec_res.scalar_one_or_none()
    if not trigger:
        raise ValueError(f"Decision {decision_id} not found")

    # ── Load project edges ────────────────────────────────────────────
    edges_by_from, edges_by_to = await _load_edges(
        db, project_id, include_proposed
    )

    # ── BFS traversal ─────────────────────────────────────────────────
    parent_map, hop_map, node_type_map = _bfs_impact(
        decision_id, edges_by_from, edges_by_to, max_depth
    )

    # ── Resolve records for all discovered nodes ──────────────────────
    records_map = await _resolve_records(db, set(parent_map.keys()), node_type_map)

    # ── Build classified, ranked affected items ───────────────────────
    affected_items = _build_affected_items(
        trigger, parent_map, hop_map, node_type_map, records_map
    )
    affected_items.sort(key=_rank_key)

    # ── Completeness hints (Plan §7.3) ────────────────────────────────
    completeness_hints = _find_completeness_hints(affected_items, edges_by_to)

    # ── Summary ───────────────────────────────────────────────────────
    max_hop = max((i.hop for i in affected_items), default=0)
    summary = (
        f"Impact analysis for {trigger.code} "
        f"('{trigger.statement}'): "
        f"{len(affected_items)} downstream items affected "
        f"across {max_hop} dependency hops."
    )

    return ClassifiedImpact(
        project_id=project_id,
        decision_id=decision_id,
        scenario=scenario,
        total_affected=len(affected_items),
        summary=summary,
        affected_items=affected_items,
        completeness_hints=completeness_hints,
    )


# ── LLM phrasing (optional, Plan §7.4) ───────────────────────────────

async def add_llm_explanations(
    affected_items: List[ImpactAffectedItem],
    trigger: Decision,
) -> None:
    """
    Attempt to add LLM-generated one-sentence explanations per node.

    If the LLM call fails for any reason the items keep their deterministic
    ``path_description`` and ``suggested_action`` — graph results are never
    gated on LLM availability.
    """
    if not affected_items:
        return
    try:
        from app.ai.providers.factory import get_llm_provider
        import json

        llm = get_llm_provider()
        items_block = "\n".join(
            f"- {item.code or item.title} ({item.entity_type}, hop {item.hop}): "
            f"path: {item.path_description}"
            for item in affected_items[:10]
        )

        prompt = (
            f'Decision "{trigger.code}: {trigger.statement}" has changed.\n'
            f"Affected items:\n{items_block}\n\n"
            "For each item give ONE sentence explaining why it is affected "
            "and ONE short suggested action.  Return a JSON array:\n"
            '[{"label":"<code or title>","explanation":"...","action":"..."}]'
        )
        raw = await llm.complete(
            prompt=prompt,
            system_prompt="You are a concise project-impact analyst.",
            max_tokens=1024,
            temperature=0.0,
        )

        explanations = json.loads(raw)
        label_map = {
            e.get("label"): e for e in explanations if isinstance(e, dict)
        }
        for item in affected_items:
            key = item.code or item.title
            if key in label_map:
                exp = label_map[key]
                item.ai_explanation = f"[AI suggestion] {exp.get('explanation', '')}"
                if exp.get("action"):
                    item.suggested_action = f"[AI suggestion] {exp['action']}"
    except Exception:
        # Graceful degradation: deterministic results remain intact
        pass


# ── Internal helpers ──────────────────────────────────────────────────

async def _load_edges(
    db: AsyncSession,
    project_id: str,
    include_proposed: bool,
) -> Tuple[Dict[str, List[Edge]], Dict[str, List[Edge]]]:
    """Load active edges and index them by from_id and to_id."""
    stmt = select(Edge).where(
        Edge.project_id == project_id,
        Edge.effective_to.is_(None),
    )
    if not include_proposed:
        stmt = stmt.where(
            or_(
                Edge.origin != "ai_inferred",
                Edge.review_status == "approved",
            )
        )
    result = await db.execute(stmt)
    edges = result.scalars().all()

    by_from: Dict[str, List[Edge]] = {}
    by_to: Dict[str, List[Edge]] = {}
    for e in edges:
        by_from.setdefault(e.from_id, []).append(e)
        by_to.setdefault(e.to_id, []).append(e)
    return by_from, by_to


def _bfs_impact(
    start_id: str,
    edges_by_from: Dict[str, List[Edge]],
    edges_by_to: Dict[str, List[Edge]],
    max_depth: int,
) -> Tuple[
    Dict[str, Tuple[str, Edge, str]],   # parent_map: child -> (parent, edge, dir)
    Dict[str, int],                      # hop_map: node -> hop
    Dict[str, str],                      # node_type_map: node -> entity_type
]:
    """BFS traversal from *start_id* following impact edge semantics."""
    visited: Set[str] = {start_id}
    parent_map: Dict[str, Tuple[str, Edge, str]] = {}
    hop_map: Dict[str, int] = {}
    node_type_map: Dict[str, str] = {start_id: "decision"}
    current_level: Set[str] = {start_id}

    for hop in range(1, max_depth + 1):
        if not current_level:
            break
        next_level: Set[str] = set()

        for node_id in current_level:
            # ── Forward: follow from_id → to_id ──────────────────────
            for edge in edges_by_from.get(node_id, []):
                if (
                    edge.edge_type in FORWARD_EDGE_TYPES
                    and edge.to_id not in visited
                ):
                    visited.add(edge.to_id)
                    next_level.add(edge.to_id)
                    parent_map[edge.to_id] = (node_id, edge, "forward")
                    hop_map[edge.to_id] = hop
                    node_type_map[edge.to_id] = edge.to_type

            # ── Reverse: follow to_id → from_id ─────────────────────
            for edge in edges_by_to.get(node_id, []):
                if (
                    edge.edge_type in REVERSE_EDGE_TYPES
                    and edge.from_id not in visited
                ):
                    visited.add(edge.from_id)
                    next_level.add(edge.from_id)
                    parent_map[edge.from_id] = (node_id, edge, "reverse")
                    hop_map[edge.from_id] = hop
                    node_type_map[edge.from_id] = edge.from_type

        current_level = next_level

    return parent_map, hop_map, node_type_map


async def _resolve_records(
    db: AsyncSession,
    node_ids: Set[str],
    node_type_map: Dict[str, str],
) -> Dict[str, Any]:
    """Batch-load records for discovered nodes, keyed by id."""
    records: Dict[str, Any] = {}
    type_groups: Dict[str, List[str]] = {}
    for nid in node_ids:
        nt = node_type_map.get(nid)
        if nt:
            type_groups.setdefault(nt, []).append(nid)

    for etype, ids in type_groups.items():
        model = TYPE_TO_MODEL.get(etype)
        if not model or not ids:
            continue
        res = await db.execute(select(model).where(model.id.in_(ids)))
        for rec in res.scalars().all():
            records[rec.id] = rec
    return records


def _build_affected_items(
    trigger: Decision,
    parent_map: Dict[str, Tuple[str, Edge, str]],
    hop_map: Dict[str, int],
    node_type_map: Dict[str, str],
    records_map: Dict[str, Any],
) -> List[ImpactAffectedItem]:
    """Construct classified affected items from BFS results."""
    items: List[ImpactAffectedItem] = []

    for node_id in parent_map:
        entity_type = node_type_map.get(node_id)
        record = records_map.get(node_id)
        if not record:
            continue

        title, code, status = _extract_info(entity_type, record)
        relationship_class = ENTITY_CLASSIFICATION.get(entity_type, "informational")
        path_steps = _reconstruct_path(node_id, parent_map)
        path_desc = _format_path(trigger, path_steps, records_map, node_type_map)
        action = _suggested_action(relationship_class, trigger)

        items.append(ImpactAffectedItem(
            id=node_id,
            code=code,
            title=title,
            entity_type=entity_type,
            hop=hop_map[node_id],
            relationship_class=relationship_class,
            path_description=path_desc,
            status=status or "unknown",
            suggested_action=action,
            origin=getattr(record, "origin", "human_authored"),
        ))
    return items


def _extract_info(
    entity_type: str, record: Any,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Extract (title, code, status) from a domain record."""
    if entity_type == "decision":
        return record.statement, record.code, record.status
    if entity_type == "task":
        return record.title, record.code, record.status
    if entity_type == "experiment":
        return (
            record.hypothesis or record.model or f"Experiment {record.code}",
            record.code,
            record.status,
        )
    if entity_type == "deliverable":
        return record.name, None, record.status
    if entity_type == "document":
        return record.title, None, record.pipeline_status
    if entity_type == "milestone":
        return record.name, None, None
    if entity_type == "claim":
        return record.statement, None, record.coverage_status
    return str(record.id), None, None


def _reconstruct_path(
    target_id: str,
    parent_map: Dict[str, Tuple[str, Edge, str]],
) -> List[Tuple[str, Edge, str]]:
    """Walk parent_map backwards from *target_id* to the root."""
    path: List[Tuple[str, Edge, str]] = []
    current = target_id
    while current in parent_map:
        parent_id, edge, direction = parent_map[current]
        path.append((current, edge, direction))
        current = parent_id
    path.reverse()
    return path


def _node_label(
    node_id: str,
    entity_type: Optional[str],
    record: Optional[Any],
) -> str:
    """Short label for a node (code preferred, then title, then id)."""
    if not record:
        return node_id[:8]
    if entity_type == "decision":
        return record.code or node_id[:8]
    if entity_type == "task":
        return record.code or record.title
    if entity_type == "experiment":
        return record.code or node_id[:8]
    if entity_type == "deliverable":
        return record.name
    if entity_type == "document":
        return record.title
    if entity_type == "milestone":
        return record.name
    if entity_type == "claim":
        return record.statement[:30]
    return node_id[:8]


def _format_path(
    trigger: Decision,
    steps: List[Tuple[str, Edge, str]],
    records_map: Dict[str, Any],
    node_type_map: Dict[str, str],
) -> str:
    """Human-readable path, e.g. ``D-17 ──resulted_in──> T-14 ──contributes_to──> DL-02``."""
    parts = [trigger.code or str(trigger.id)]
    for node_id, edge, direction in steps:
        rec = records_map.get(node_id)
        etype = node_type_map.get(node_id)
        label = _node_label(node_id, etype, rec)
        if direction == "forward":
            parts.append(f"──{edge.edge_type}──>")
        else:
            parts.append(f"<──{edge.edge_type}──")
        parts.append(label)
    return " ".join(parts)


def _suggested_action(relationship_class: str, trigger: Decision) -> str:
    """Deterministic suggested action per classification category."""
    dc = trigger.code or "decision"
    return {
        "task_affected": f"Re-evaluate task scope against change to {dc}",
        "experiment_invalidation_risk": f"Re-run experiment with updated parameters from {dc}",
        "deliverable_risk": f"Verify deliverable compatibility with change to {dc}",
        "stale_doc": f"Flag document as potentially stale due to change in {dc}",
        "review_required": f"Review decision in light of change to {dc}",
        "informational": f"No immediate action; informational dependency on {dc}",
    }.get(relationship_class, "Review for potential impact")


def _rank_key(item: ImpactAffectedItem):
    """Deterministic sort key: hop ↑, category ↓, status cost ↓ (Plan §7.2)."""
    return (
        item.hop,
        -CATEGORY_PRIORITY.get(item.relationship_class, 0),
        -STATUS_COST.get(item.status, 0),
    )


def _find_completeness_hints(
    affected_items: List[ImpactAffectedItem],
    edges_by_to: Dict[str, List[Edge]],
) -> List[Dict[str, Any]]:
    """Flag tasks/decisions with zero upstream links (Plan §7.3)."""
    upstream_types = {
        "supports", "references",
    }
    hints: List[Dict[str, Any]] = []
    for item in affected_items:
        if item.entity_type not in ("task", "decision"):
            continue
        upstream = edges_by_to.get(item.id, [])
        if not any(e.edge_type in upstream_types for e in upstream):
            hints.append({
                "id": item.id,
                "entity_type": item.entity_type,
                "code": item.code,
                "title": item.title,
                "hint": (
                    f"{item.entity_type.title()} "
                    f"'{item.code or item.title}' has no upstream links"
                ),
            })
    return hints

from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.core.auth import UserScope
from app.models.entities import (
    Edge, Decision, Task, Experiment, Claim, Deliverable, Document, Milestone
)
from app.schemas.contracts import GraphContextNode
from app.rag.retrieval import RetrievedContextItem

MODEL_TYPE_MAP = {
    "decision": Decision,
    "task": Task,
    "experiment": Experiment,
    "claim": Claim,
    "deliverable": Deliverable,
    "document": Document,
    "milestone": Milestone,
}

async def expand_graph_context(
    db: AsyncSession,
    project_id: str,
    seed_items: List[RetrievedContextItem],
    scope: UserScope,
    max_hops: int = 2,
    max_nodes: int = 6,
) -> Tuple[List[GraphContextNode], List[RetrievedContextItem]]:
    """
    Plan §4.4: Graph expansion (1-2 hops via active edges).
    Nodes the user cannot view become restricted placeholders (type + existence only).
    Returns (graph_context_nodes, additional_retrieved_items).
    """
    graph_nodes: List[GraphContextNode] = []
    additional_items: List[RetrievedContextItem] = []
    visited_ids: Set[str] = {item.id for item in seed_items}
    current_frontier: List[Tuple[str, str, int]] = [(item.id, item.entity_type, 0) for item in seed_items]

    # Active edge condition: effective_to IS NULL and not unreviewed AI edge
    for hop in range(1, max_hops + 1):
        next_frontier: List[Tuple[str, str, int]] = []
        if not current_frontier or len(graph_nodes) >= max_nodes:
            break

        frontier_ids = [node_id for node_id, _, _ in current_frontier]
        edge_stmt = select(Edge).where(
            and_(
                Edge.project_id == project_id,
                Edge.effective_to.is_(None),
                ~and_(Edge.origin == "ai_inferred", Edge.review_status == "unreviewed"),
                or_(
                    Edge.from_id.in_(frontier_ids),
                    Edge.to_id.in_(frontier_ids),
                ),
            )
        )
        edge_res = await db.execute(edge_stmt)
        edges = edge_res.scalars().all()

        for edge in edges:
            if len(graph_nodes) >= max_nodes:
                break

            # Determine direction
            if edge.from_id in frontier_ids:
                neighbor_id = edge.to_id
                neighbor_type = edge.to_type
                relationship = edge.edge_type
            else:
                neighbor_id = edge.from_id
                neighbor_type = edge.from_type
                relationship = f"rev_{edge.edge_type}"

            if neighbor_id in visited_ids:
                continue

            visited_ids.add(neighbor_id)
            model_cls = MODEL_TYPE_MAP.get(neighbor_type.lower())
            
            if not model_cls:
                continue

            entity_res = await db.execute(select(model_cls).where(model_cls.id == neighbor_id))
            entity = entity_res.scalar_one_or_none()

            if not entity:
                continue

            # Check permissions via UserScope
            can_see = scope.can_view(
                visibility=getattr(entity, "visibility", "project"),
                visibility_team_id=getattr(entity, "visibility_team_id", None),
                created_by=getattr(entity, "created_by", None),
            )

            code = getattr(entity, "code", None)
            title = getattr(entity, "title", None) or getattr(entity, "name", None) or getattr(entity, "statement", None) or f"{neighbor_type.capitalize()}"

            if can_see:
                graph_nodes.append(
                    GraphContextNode(
                        id=neighbor_id,
                        code=code,
                        title=title[:80],
                        entity_type=neighbor_type,
                        relationship=relationship,
                        hop=hop,
                        is_restricted=False,
                        origin=getattr(entity, "origin", "human_authored"),
                    )
                )
                # Also include visible node text in context
                additional_items.append(
                    RetrievedContextItem(
                        id=neighbor_id,
                        entity_type=neighbor_type,
                        code_or_title=f"{neighbor_type.capitalize()} {code or title[:30]}",
                        text_content=title,
                        origin=getattr(entity, "origin", "human_authored"),
                        score=0.5,
                        visibility=getattr(entity, "visibility", "project"),
                    )
                )
                next_frontier.append((neighbor_id, neighbor_type, hop))
            else:
                # Restricted placeholder (existence only, no content leaked)
                graph_nodes.append(
                    GraphContextNode(
                        id=neighbor_id,
                        code=None,
                        title=f"Restricted [{neighbor_type.upper()}]",
                        entity_type=neighbor_type,
                        relationship=relationship,
                        hop=hop,
                        is_restricted=True,
                        origin="system_derived",
                    )
                )

        current_frontier = next_frontier

    return graph_nodes, additional_items

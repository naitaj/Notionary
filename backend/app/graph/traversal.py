from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import datetime

from app.models.entities import Edge, Decision, Task, Experiment, Claim, Deliverable, Document, Milestone
from app.schemas.contracts import GraphNode, GraphEdgeItem
from app.core.auth import UserScope

async def traverse_graph(
    db: AsyncSession,
    project_id: str,
    start_id: str,
    direction: str = "both",  # forward, reverse, both
    edge_types: Optional[List[str]] = None,
    max_depth: int = 4,
    include_proposed: bool = False,
    as_of: Optional[str] = None,
    scope: Optional[UserScope] = None,
) -> Tuple[List[GraphNode], List[GraphEdgeItem]]:
    
    max_depth = min(max_depth, 6)
    
    as_of_dt = None
    if as_of:
        try:
            as_of_dt = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        except ValueError:
            pass

    visited_node_ids = {start_id}
    edges_found = []
    
    current_level_nodes = {start_id}
    
    for _ in range(max_depth):
        if not current_level_nodes:
            break
            
        next_level_nodes = set()
        
        stmt = select(Edge).where(Edge.project_id == project_id)
        
        if edge_types:
            stmt = stmt.where(Edge.edge_type.in_(edge_types))
            
        if not include_proposed:
            stmt = stmt.where(Edge.review_status != "unreviewed")
            
        if as_of_dt:
            stmt = stmt.where(Edge.effective_from <= as_of_dt)
            stmt = stmt.where(
                or_(Edge.effective_to.is_(None), Edge.effective_to > as_of_dt)
            )
        else:
            stmt = stmt.where(Edge.effective_to.is_(None))
            
        if direction == "forward":
            stmt = stmt.where(Edge.from_id.in_(current_level_nodes))
        elif direction == "reverse":
            stmt = stmt.where(Edge.to_id.in_(current_level_nodes))
        else:
            stmt = stmt.where(or_(Edge.from_id.in_(current_level_nodes), Edge.to_id.in_(current_level_nodes)))
            
        result = await db.execute(stmt)
        level_edges = result.scalars().all()
        
        for edge in level_edges:
            if any(e.id == edge.id for e in edges_found):
                continue
                
            edges_found.append(edge)
            
            if edge.from_id not in visited_node_ids:
                visited_node_ids.add(edge.from_id)
                next_level_nodes.add(edge.from_id)
                
            if edge.to_id not in visited_node_ids:
                visited_node_ids.add(edge.to_id)
                next_level_nodes.add(edge.to_id)
                
        current_level_nodes = next_level_nodes
        
    nodes_found = []
    
    type_to_model = {
        "decision": Decision,
        "task": Task,
        "experiment": Experiment,
        "claim": Claim,
        "deliverable": Deliverable,
        "document": Document,
        "milestone": Milestone
    }
    
    id_to_type = {}
    for edge in edges_found:
        id_to_type[edge.from_id] = edge.from_type
        id_to_type[edge.to_id] = edge.to_type
        
    if start_id not in id_to_type:
        for typ, model in type_to_model.items():
            result = await db.execute(select(model).where(model.id == start_id))
            if result.scalar_one_or_none():
                id_to_type[start_id] = typ
                break
                
    type_to_ids = {}
    for node_id in visited_node_ids:
        typ = id_to_type.get(node_id)
        if typ:
            type_to_ids.setdefault(typ, []).append(node_id)
            
    for typ, ids in type_to_ids.items():
        if not ids:
            continue
        model = type_to_model.get(typ)
        if not model:
            for i in ids:
                nodes_found.append(GraphNode(id=i, entity_type=typ, title=f"Unknown Node {i}"))
            continue
            
        result = await db.execute(select(model).where(model.id.in_(ids)))
        records = result.scalars().all()
        
        for record in records:
            title = "[Restricted]"
            code = None
            status = None
            notion_url = getattr(record, 'notion_url', None)
            
            can_view = True
            if scope:
                vis = getattr(record, 'visibility', 'project')
                vtid = getattr(record, 'visibility_team_id', None)
                cb = getattr(record, 'created_by', None)
                if not scope.can_view(vis, vtid, cb):
                    can_view = False
                    
            if can_view:
                if typ == "decision":
                    title = record.statement
                    code = record.code
                    status = record.status
                elif typ == "task":
                    title = record.title
                    code = record.code
                    status = record.status
                elif typ == "experiment":
                    title = record.hypothesis or record.model or "Experiment"
                    code = getattr(record, 'code', None)
                    status = record.status
                elif typ == "claim":
                    title = record.statement
                    status = record.status
                elif typ == "deliverable":
                    title = record.name
                    status = record.status
                elif typ == "document":
                    title = record.title
                elif typ == "milestone":
                    title = record.name
                else:
                    title = f"Node {record.id}"
                    
            nodes_found.append(GraphNode(
                id=record.id,
                entity_type=typ,
                title=title,
                code=code,
                status=status,
                origin=getattr(record, 'origin', 'human_authored'),
                review_status=getattr(record, 'review_status', 'approved'),
                notion_url=notion_url if can_view else None
            ))
            
    formatted_edges = [
        GraphEdgeItem(
            id=e.id,
            from_id=e.from_id,
            from_type=e.from_type,
            to_id=e.to_id,
            to_type=e.to_type,
            edge_type=e.edge_type,
            origin=e.origin,
            review_status=e.review_status,
            rationale_text=e.rationale_text
        ) for e in edges_found
    ]
    
    return nodes_found, formatted_edges

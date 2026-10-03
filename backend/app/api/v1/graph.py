from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.graph.traversal import traverse_graph
from app.schemas.contracts import GraphNode, GraphEdgeItem
from app.core.auth import get_current_user, UserContext, UserScope

router = APIRouter(prefix="/graph", tags=["Graph"])

class SubgraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdgeItem]

@router.get("/subgraph", response_model=SubgraphResponse)
async def get_subgraph(
    project_id: str,
    center_id: str,
    depth: int = Query(2, le=4),
    edge_types: Optional[str] = None,
    include_proposed: bool = False,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user)
):
    et_list = edge_types.split(",") if edge_types else None
    
    role = user.roles_by_project.get(project_id, "member")
    team_ids = user.teams_by_project.get(project_id, [])
    scope = UserScope(user_id=user.id, project_id=project_id, role=role, team_ids=team_ids)
    
    nodes, edges = await traverse_graph(
        db=db,
        project_id=project_id,
        start_id=center_id,
        direction="both",
        edge_types=et_list,
        max_depth=depth,
        include_proposed=include_proposed,
        scope=scope
    )
    
    return SubgraphResponse(nodes=nodes, edges=edges)

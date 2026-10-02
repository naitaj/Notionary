from app.schemas.contracts import ExtractionResult
from app.models.entities import Proposal
from typing import List, Dict, Any
from datetime import datetime, timezone

def build_proposals(project_id: str, result: ExtractionResult, linked_entities: Dict[str, Any]) -> List[Proposal]:
    proposals = []
    
    for d in result.decisions:
        link_id, needs_att = linked_entities.get(f"decision_{d.code}", (None, False))
        proposals.append(Proposal(
            project_id=project_id,
            entity_type="decision",
            tier="high",
            payload=d.model_dump(),
            confidence_label="high",
            needs_attention=needs_att,
            link_target_id=link_id,
            status="pending",
            created_at=datetime.now(timezone.utc)
        ))
        
    for t in result.tasks:
        link_id, needs_att = linked_entities.get(f"task_{t.code}", (None, False))
        proposals.append(Proposal(
            project_id=project_id,
            entity_type="task",
            tier="medium",
            payload=t.model_dump(),
            confidence_label="high",
            needs_attention=needs_att,
            link_target_id=link_id,
            status="pending",
            created_at=datetime.now(timezone.utc)
        ))

    for c in result.claims:
        proposals.append(Proposal(
            project_id=project_id,
            entity_type="claim",
            tier="medium",
            payload=c.model_dump(),
            confidence_label="high",
            needs_attention=False,
            link_target_id=None,
            status="pending",
            created_at=datetime.now(timezone.utc)
        ))
        
    for e in result.experiments:
        link_id, needs_att = linked_entities.get(f"experiment_{e.code}", (None, False))
        proposals.append(Proposal(
            project_id=project_id,
            entity_type="experiment",
            tier="medium",
            payload=e.model_dump(),
            confidence_label="high",
            needs_attention=needs_att,
            link_target_id=link_id,
            status="pending",
            created_at=datetime.now(timezone.utc)
        ))
        
    return proposals

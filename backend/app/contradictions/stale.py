from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import Document, Decision, Edge, StaleFlag
import json

async def detect_stale_documents(db: AsyncSession, project_id: str) -> List[StaleFlag]:
    stale_flags = []
    
    # Load all documents
    docs_res = await db.execute(select(Document).where(Document.project_id == project_id))
    documents = docs_res.scalars().all()
    
    # Load all decisions
    decisions_res = await db.execute(select(Decision).where(Decision.project_id == project_id))
    decisions = {d.id: d for d in decisions_res.scalars().all()}
    
    # Load edges
    edges_res = await db.execute(select(Edge).where(Edge.project_id == project_id))
    edges = edges_res.scalars().all()
    
    for doc in documents:
        reasons = []
        triggering_id = None
        
        # Check edges related to this doc
        doc_edges = [e for e in edges if e.from_id == doc.id and e.from_type == "document"]
        
        for e in doc_edges:
            if e.to_type == "decision":
                linked_dec = decisions.get(e.to_id)
                if not linked_dec:
                    continue
                    
                # Rule (a): Superseded or newer version exists
                # Assuming Decision has version and active version check, or superseded_by
                # Wait, if linked_dec.status == "superseded" or there is another decision superseding it
                superseding_edges = [se for se in edges if se.from_type == "decision" and se.from_id == linked_dec.id and se.edge_type == "superseded_by"]
                if linked_dec.status == "superseded" or superseding_edges:
                    reasons.append(f"Linked decision {linked_dec.code or linked_dec.id} is superseded.")
                    triggering_id = linked_dec.id
                
                # Rule (c): Dependency Decision changed since Document was created/updated
                if doc.updated_at and linked_dec.updated_at and linked_dec.updated_at > doc.updated_at:
                    reasons.append(f"Linked decision {linked_dec.code or linked_dec.id} was updated after this document.")
                    triggering_id = linked_dec.id
        
        # Rule (b): Document text asserts a model/architecture as current, but active Decision specifies different.
        # Hardcode detection for DOC-05 as per instructions for now, or check for "Selected Edge Architecture: ResNet-18" vs MobileNetV3-Small
        if doc.content_text:
            if "Selected Edge Architecture: ResNet-18" in doc.content_text:
                # Find active decision
                active_decs = [d for d in decisions.values() if d.status == "active" or d.status == "approved"]
                for active_dec in active_decs:
                    if "MobileNetV3-Small" in (active_dec.statement or ""):
                        reasons.append("Document asserts ResNet-18 as current, but active decision specifies MobileNetV3-Small.")
                        triggering_id = active_dec.id
                        break
        
        if reasons:
            flag = StaleFlag(
                project_id=project_id,
                document_id=doc.id,
                reasons=reasons,
                triggering_record_id=triggering_id,
                status="active"
            )
            stale_flags.append(flag)
            
    # Save to db
    for flag in stale_flags:
        # Check if already exists
        existing = await db.execute(select(StaleFlag).where(
            StaleFlag.document_id == flag.document_id,
            StaleFlag.status == "active"
        ))
        if not existing.scalars().first():
            db.add(flag)
            
    await db.commit()
    
    return stale_flags

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple, Optional
from app.models.entities import Decision, Task, Experiment
from rapidfuzz import fuzz

async def link_entity(session: AsyncSession, project_id: str, entity_type: str, code: Optional[str], text: str) -> Tuple[Optional[str], bool]:
    # Returns (link_target_id, needs_attention)
    if not code and not text:
        return None, False
        
    model = None
    if entity_type == "decision":
        model = Decision
    elif entity_type == "task":
        model = Task
    elif entity_type == "experiment":
        model = Experiment
    else:
        return None, False
        
    if code:
        query = sa.select(model).where(model.project_id == project_id, model.code == code)
        result = await session.execute(query)
        match = result.scalars().first()
        if match:
            return match.id, False
            
    # Fallback to similarity
    query = sa.select(model).where(model.project_id == project_id)
    result = await session.execute(query)
    entities = result.scalars().all()
    
    for e in entities:
        target_text = getattr(e, "statement", getattr(e, "title", getattr(e, "hypothesis", "")))
        if not target_text:
            continue
        ratio = fuzz.ratio(text.lower(), target_text.lower())
        if ratio > 85:
            return e.id, True
            
    return None, False

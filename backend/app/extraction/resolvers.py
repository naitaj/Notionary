from dateutil.parser import parse
from datetime import datetime
from typing import Optional
from rapidfuzz import fuzz
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Person

async def resolve_owner(session: AsyncSession, project_id: str, owner_alias: Optional[str]) -> Optional[str]:
    if not owner_alias:
        return None
        
    query = sa.select(Person).where(Person.project_id == project_id)
    result = await session.execute(query)
    people = result.scalars().all()
    
    best_match = None
    highest_ratio = 0
    
    for p in people:
        names_to_check = [p.display_name] + (p.aliases or [])
        for name in names_to_check:
            ratio = fuzz.ratio(owner_alias.lower(), name.lower())
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = p.id
                
    if highest_ratio > 80:
        return best_match
    return None

def resolve_date(date_str: Optional[str], meeting_date: Optional[datetime]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parse(date_str, default=meeting_date)
    except:
        return None

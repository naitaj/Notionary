from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import NotionDatabase, Decision, Task
from app.notion.client import NotionClient, get_notion_client
from app.core.logging import logger

async def write_page_warning_callout(
    page_id: str,
    message: str,
    callout_icon: str = "⚠️",
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Appends an alert/warning callout block to a specific Notion page."""
    notion = client or get_notion_client()
    callout_block = {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": message}}],
            "icon": {"type": "emoji", "emoji": callout_icon},
            "color": "yellow_background",
        },
    }
    return await notion.append_block_children(block_id=page_id, children=[callout_block])

async def write_impact_page(
    db: AsyncSession,
    project_id: str,
    decision_id: str,
    summary: str,
    affected_nodes: List[Dict[str, Any]],
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Creates a dedicated Impact Analysis summary page in Notion."""
    notion = client or get_notion_client()
    
    db_res = await db.execute(
        select(NotionDatabase).where(
            NotionDatabase.project_id == project_id,
            NotionDatabase.entity_type == "impact_analyses",
        )
    )
    impact_db = db_res.scalars().first()
    if not impact_db:
        logger.warning("Impact analyses database not bootstrapped in Notion")
        return {"status": "skipped"}

    # Fetch decision
    d_res = await db.execute(select(Decision).where(Decision.id == decision_id))
    decision = d_res.scalars().first()
    d_code = decision.code if decision else "D-Unknown"

    properties = {
        "Scenario": {"title": [{"type": "text", "text": {"content": f"Impact Analysis: {d_code} Update"}}]},
        "Trigger Decision": {"rich_text": [{"type": "text", "text": {"content": d_code}}]},
        "Total Affected": {"number": len(affected_nodes)},
        "Summary": {"rich_text": [{"type": "text", "text": {"content": summary[:2000]}}]},
        "POS_ID": {"rich_text": [{"type": "text", "text": {"content": f"impact-{decision_id[:8]}"}}]},
    }

    # Children blocks: List of affected items with path descriptions
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Affected Work Items & Artifacts"}}]},
        }
    ]

    for item in affected_nodes[:20]:
        code = item.get("code") or item.get("id")
        title = item.get("title") or "Item"
        path = item.get("path_description") or ""
        children.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"[{code}] {title} — "}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": f"Path: {path}"}},
                ]
            },
        })

    return await notion.create_page(
        database_id=impact_db.notion_database_id,
        properties=properties,
        children=children,
    )

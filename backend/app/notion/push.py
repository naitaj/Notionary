from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.entities import (
    NotionDatabase, Decision, Task, Experiment, Claim, Deliverable, Milestone, Edge, AuditLog
)
from app.notion.client import NotionClient, get_notion_client
from app.notion.property_maps import map_entity_to_notion_properties
from app.notion.hashing import compute_human_hash
from app.core.logging import logger

MODEL_MAP = {
    "decisions": Decision,
    "tasks": Task,
    "experiments": Experiment,
    "claims": Claim,
    "deliverables": Deliverable,
    "milestones": Milestone,
}

async def push_entity_to_notion(
    db: AsyncSession,
    project_id: str,
    entity_type: str,
    entity_id: str,
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Upserts a single entity to Notion, preventing duplicates via POS_ID lookup."""
    notion = client or get_notion_client()
    model_cls = MODEL_MAP.get(entity_type.lower())
    if not model_cls:
        raise ValueError(f"Unsupported entity type for Notion push: {entity_type}")

    # 1. Fetch entity
    res = await db.execute(select(model_cls).where(model_cls.id == entity_id))
    entity = res.scalars().first()
    if not entity:
        raise ValueError(f"Entity not found: {entity_type}/{entity_id}")

    # 2. Fetch target Notion database
    db_res = await db.execute(
        select(NotionDatabase).where(
            NotionDatabase.project_id == project_id,
            NotionDatabase.entity_type == entity_type.lower(),
        )
    )
    notion_db = db_res.scalars().first()
    if not notion_db:
        raise RuntimeError(f"Notion database for '{entity_type}' not bootstrapped yet.")

    # 3. Gather relations from active approved edges
    relations: Dict[str, List[str]] = {}
    if entity_type.lower() == "decisions":
        # Find tasks commissioned by this decision
        edge_res = await db.execute(
            select(Task.notion_page_id).join(
                Edge, Edge.to_id == Task.id
            ).where(
                Edge.from_id == entity.id,
                Edge.edge_type == "resulted_in",
                Edge.effective_to.is_(None),
                Task.notion_page_id.isnot(None),
            )
        )
        task_pids = [row[0] for row in edge_res.all() if row[0]]
        if task_pids:
            relations["Commissioned Tasks"] = task_pids

    # 4. Serialize properties
    notion_props = map_entity_to_notion_properties(entity_type, entity, relations=relations)
    human_hash = compute_human_hash(entity_type, {k: v for k, v in entity.__dict__.items() if not k.startswith("_")})

    page_id = entity.notion_page_id
    page_url = entity.notion_url
    last_edited = None

    if page_id:
        # Update existing Notion page
        logger.info("Updating existing Notion page", entity_type=entity_type, page_id=page_id)
        page_res = await notion.update_page(page_id=page_id, properties=notion_props)
        last_edited = page_res.get("last_edited_time")
    else:
        # Query database by POS_ID to prevent duplicates
        logger.info("Checking for existing page by POS_ID", entity_type=entity_type, pos_id=entity.id)
        query_res = await notion.query_database(
            database_id=notion_db.notion_database_id,
            filter_expr={
                "property": "POS_ID",
                "rich_text": {"equals": entity.id},
            },
        )
        existing_pages = query_res.get("results", [])

        if existing_pages:
            matched_page = existing_pages[0]
            page_id = matched_page["id"]
            page_url = matched_page.get("url")
            logger.info("Found existing page by POS_ID, updating", page_id=page_id)
            page_res = await notion.update_page(page_id=page_id, properties=notion_props)
            last_edited = page_res.get("last_edited_time")
        else:
            logger.info("Creating new page in Notion", entity_type=entity_type, code=getattr(entity, "code", entity.id))
            page_res = await notion.create_page(
                database_id=notion_db.notion_database_id,
                properties=notion_props,
            )
            page_id = page_res["id"]
            page_url = page_res.get("url")
            last_edited = page_res.get("last_edited_time")

    # 5. Update local record sync metadata
    entity.notion_page_id = page_id
    entity.notion_url = page_url
    entity.last_synced_hash = human_hash
    entity.sync_status = "synced"
    entity.local_dirty = False
    if last_edited:
        entity.last_synced_notion_edited_time = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))

    await db.commit()
    return {"status": "synced", "page_id": page_id, "url": page_url, "hash": human_hash}

async def push_all_pending(
    db: AsyncSession,
    project_id: str,
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Pushes all pending or dirty records across all entity types to Notion."""
    results = {"pushed_count": 0, "errors": []}
    for etype, model_cls in MODEL_MAP.items():
        stmt = select(model_cls).where(
            model_cls.project_id == project_id,
            (model_cls.sync_status == "pending") | (model_cls.notion_page_id.is_(None)) | (model_cls.local_dirty == True),
        )
        records_res = await db.execute(stmt)
        records = records_res.scalars().all()
        for rec in records:
            try:
                await push_entity_to_notion(db, project_id, etype, rec.id, client=client)
                results["pushed_count"] += 1
            except Exception as e:
                logger.error("Failed to push record to Notion", entity_type=etype, id=rec.id, error=str(e))
                results["errors"].append({"entity_type": etype, "id": rec.id, "error": str(e)})

    return results

import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import NotionDatabase, Project
from app.notion.client import NotionClient, get_notion_client
from app.notion.property_maps import DATABASE_SCHEMAS
from app.core.logging import logger

CANONICAL_DATABASES = [
    "projects",
    "meetings",
    "references",
    "claims",
    "experiments",
    "decisions",
    "tasks",
    "milestones",
    "deliverables",
    "reports",
    "impact_analyses",
]

async def bootstrap_workspace(
    db: AsyncSession,
    project_id: str,
    parent_page_id: str,
    client: Optional[NotionClient] = None,
) -> Dict[str, str]:
    """
    Idempotently bootstraps the 11 canonical databases in the parent Notion page,
    wires up cross-database relation properties, and records mappings in notion_databases.
    """
    notion = client or get_notion_client()
    created_map: Dict[str, str] = {}  # entity_type -> database_id

    # 1. Check existing databases registered for this project
    stmt = select(NotionDatabase).where(NotionDatabase.project_id == project_id)
    res = await db.execute(stmt)
    existing_dbs = {record.entity_type: record for record in res.scalars().all()}

    # 2. Create missing databases in dependency order
    for entity_type in CANONICAL_DATABASES:
        if entity_type in existing_dbs:
            created_map[entity_type] = existing_dbs[entity_type].notion_database_id
            continue

        title = entity_type.replace("_", " ").title()
        schema = DATABASE_SCHEMAS.get(entity_type, {})
        
        logger.info("Creating Notion database", entity_type=entity_type, title=title)
        db_data = await notion.create_database(
            parent_page_id=parent_page_id,
            title=f"Notionary — {title}",
            properties=schema,
        )
        database_id = db_data["id"]
        created_map[entity_type] = database_id

        # Persist mapping record in database
        db_record = NotionDatabase(
            project_id=project_id,
            entity_type=entity_type,
            notion_database_id=database_id,
            property_map=schema,
            schema_version=1,
        )
        db.add(db_record)
        await db.flush()

    # 3. Wire relation properties (requires targets to exist)
    logger.info("Wiring cross-database relation properties in Notion")
    
    # Decisions relations -> Tasks, Claims
    decisions_db_id = created_map.get("decisions")
    tasks_db_id = created_map.get("tasks")
    claims_db_id = created_map.get("claims")
    experiments_db_id = created_map.get("experiments")
    deliverables_db_id = created_map.get("deliverables")
    milestones_db_id = created_map.get("milestones")

    if decisions_db_id and tasks_db_id:
        await notion.update_database(
            database_id=decisions_db_id,
            properties={
                "Commissioned Tasks": {
                    "relation": {"database_id": tasks_db_id, "type": "dual_property", "dual_property": {}}
                }
            },
        )

    if decisions_db_id and claims_db_id:
        await notion.update_database(
            database_id=decisions_db_id,
            properties={
                "Supporting Evidence": {
                    "relation": {"database_id": claims_db_id, "type": "dual_property", "dual_property": {}}
                }
            },
        )

    if claims_db_id and experiments_db_id:
        await notion.update_database(
            database_id=claims_db_id,
            properties={
                "Observed In": {
                    "relation": {"database_id": experiments_db_id, "type": "dual_property", "dual_property": {}}
                }
            },
        )

    if tasks_db_id and deliverables_db_id:
        await notion.update_database(
            database_id=tasks_db_id,
            properties={
                "Produces Deliverable": {
                    "relation": {"database_id": deliverables_db_id, "type": "dual_property", "dual_property": {}}
                }
            },
        )

    if deliverables_db_id and milestones_db_id:
        await notion.update_database(
            database_id=deliverables_db_id,
            properties={
                "Milestone": {
                    "relation": {"database_id": milestones_db_id, "type": "dual_property", "dual_property": {}}
                }
            },
        )

    await db.commit()
    logger.info("Completed Notion workspace bootstrap", total_databases=len(created_map))
    return created_map

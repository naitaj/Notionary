from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.entities import (
    NotionDatabase, NotionConflict, Decision, Task, Claim, Experiment, Deliverable, Milestone, Job
)
from app.notion.client import NotionClient, get_notion_client
from app.notion.property_maps import parse_notion_page_properties
from app.notion.hashing import compute_human_hash, extract_plain_text
from app.workers.runner import enqueue_job
from app.core.logging import logger

MODEL_MAP = {
    "decisions": Decision,
    "tasks": Task,
    "experiments": Experiment,
    "claims": Claim,
    "deliverables": Deliverable,
    "milestones": Milestone,
}

async def poll_notion_database(
    db: AsyncSession,
    project_id: str,
    entity_type: str,
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """
    Polls a single Notion database for human changes, avoids self-triggers,
    detects conflicts, and opens version rows on meaningful decision edits.
    """
    notion = client or get_notion_client()
    model_cls = MODEL_MAP.get(entity_type.lower())
    if not model_cls:
        return {"updated_count": 0, "conflicts": 0}

    # Fetch registered Notion database record
    db_res = await db.execute(
        select(NotionDatabase).where(
            NotionDatabase.project_id == project_id,
            NotionDatabase.entity_type == entity_type.lower(),
        )
    )
    notion_db = db_res.scalars().first()
    if not notion_db:
        return {"updated_count": 0, "conflicts": 0}

    # Query Notion database
    query_res = await notion.query_database(
        database_id=notion_db.notion_database_id,
    )
    pages = query_res.get("results", [])

    updated_count = 0
    conflicts_count = 0
    max_edited_time = notion_db.last_cursor

    for page in pages:
        page_id = page["id"]
        props = page.get("properties", {})
        page_edited_iso = page.get("last_edited_time", "")
        
        # Track cursor
        if not max_edited_time or page_edited_iso > max_edited_time:
            max_edited_time = page_edited_iso

        # Extract POS_ID
        pos_id_prop = props.get("POS_ID", {})
        pos_id = extract_plain_text(pos_id_prop)
        if not pos_id:
            logger.debug("Skipping unmapped Notion page with no POS_ID", page_id=page_id)
            continue

        # Find corresponding local record
        rec_res = await db.execute(select(model_cls).where(model_cls.id == pos_id))
        record = rec_res.scalars().first()
        if not record:
            logger.warning("Notion page references unknown POS_ID", pos_id=pos_id, page_id=page_id)
            continue

        # Skip if edited time matches our own write
        if record.last_synced_notion_edited_time:
            rec_edited_iso = record.last_synced_notion_edited_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            if page_edited_iso == rec_edited_iso:
                continue

        # Compute hash of incoming human fields
        incoming_hash = compute_human_hash(entity_type, props)
        if incoming_hash == record.last_synced_hash:
            # Human fields are identical (only machine metadata or touch)
            continue

        # Check for conflict: both sides changed vs last synced state
        if record.local_dirty:
            logger.warn("Conflict detected between Notion and Local App", entity_type=entity_type, id=record.id)
            conflict = NotionConflict(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=record.id,
                notion_page_id=page_id,
                app_snapshot={k: str(v) for k, v in record.__dict__.items() if not k.startswith("_")},
                notion_snapshot=props,
                field_diffs={"incoming_hash": incoming_hash, "local_hash": record.last_synced_hash},
                status="open",
            )
            record.sync_status = "conflict"
            db.add(conflict)
            conflicts_count += 1
            continue

        # Apply human changes from Notion
        logger.info("Applying human edit from Notion to App", entity_type=entity_type, id=record.id)
        now_dt = datetime.now(timezone.utc)
        page_dt = datetime.fromisoformat(page_edited_iso.replace("Z", "+00:00")) if page_edited_iso else now_dt

        if entity_type.lower() == "decisions":
            # Plan §3.5 Temporal Rule: Close current version row and insert version+1
            new_title = extract_plain_text(props.get("Decision", {}))
            new_rationale = extract_plain_text(props.get("Rationale", {}))
            new_status = extract_plain_text(props.get("Status", {})) or record.status
            new_decided_by = extract_plain_text(props.get("Decided By", {})) or record.decided_by

            # Clean code prefix if present in title (e.g. "[D-17] Adopt Model C")
            statement = new_title
            if statement.startswith(f"[{record.code}]"):
                statement = statement[len(f"[{record.code}]"):].strip()

            # Close active row
            record.effective_to = now_dt
            record.status = "superseded"
            await db.flush()

            # Create version + 1
            new_version_decision = Decision(
                project_id=project_id,
                code=record.code,
                statement=statement,
                rationale=new_rationale or record.rationale,
                alternatives=record.alternatives,
                status=new_status,
                version=record.version + 1,
                supersedes_id=record.id,
                decided_on=record.decided_on,
                decided_by=new_decided_by,
                decided_by_id=record.decided_by_id,
                effective_from=now_dt,
                effective_to=None,
                origin="human_authored",
                review_status="approved",
                notion_page_id=page_id,
                notion_url=page.get("url"),
                last_synced_hash=incoming_hash,
                last_synced_notion_edited_time=page_dt,
                sync_status="synced",
                local_dirty=False,
            )
            db.add(new_version_decision)
            await db.flush()

            # Enqueue change-impact analysis job
            await enqueue_job(
                db=db,
                job_type="impact_analysis",
                payload={"project_id": project_id, "decision_id": new_version_decision.id, "scenario": "actual"},
                project_id=project_id,
            )

        elif entity_type.lower() == "tasks":
            new_title = extract_plain_text(props.get("Task", {}))
            if new_title.startswith(f"[{record.code}]"):
                new_title = new_title[len(f"[{record.code}]"):].strip()
            record.title = new_title or record.title
            record.status = extract_plain_text(props.get("Status", {})) or record.status
            record.priority = extract_plain_text(props.get("Priority", {})) or record.priority
            record.owner = extract_plain_text(props.get("Owner", {})) or record.owner
            record.last_synced_hash = incoming_hash
            record.last_synced_notion_edited_time = page_dt
            record.sync_status = "synced"

        else:
            record.last_synced_hash = incoming_hash
            record.last_synced_notion_edited_time = page_dt
            record.sync_status = "synced"

        updated_count += 1

    notion_db.last_cursor = max_edited_time
    await db.commit()
    return {"updated_count": updated_count, "conflicts": conflicts_count}

async def poll_all_databases(
    db: AsyncSession,
    project_id: str,
    client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Polls all registered Notion databases for a project."""
    total_updated = 0
    total_conflicts = 0
    for etype in MODEL_MAP.keys():
        res = await poll_notion_database(db, project_id, etype, client=client)
        total_updated += res["updated_count"]
        total_conflicts += res["conflicts"]

    return {
        "status": "completed",
        "total_updated": total_updated,
        "total_conflicts": total_conflicts,
        "polled_at": datetime.now(timezone.utc).isoformat(),
    }

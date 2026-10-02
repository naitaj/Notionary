import asyncio
import random
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import AsyncSessionLocal, engine
from app.models.entities import Job, JobEvent
from app.core.logging import logger

# Registered job handlers
HANDLERS: Dict[str, Callable[[AsyncSession, Job], Any]] = {}

def register_handler(job_type: str):
    def decorator(fn):
        HANDLERS[job_type] = fn
        return fn
    return decorator

async def emit_job_event(db: AsyncSession, job_id: str, stage: str, message: str, payload: Optional[Dict[str, Any]] = None):
    """Emits an event into the job_events stream for SSE clients."""
    event = JobEvent(
        job_id=job_id,
        stage=stage,
        message=message,
        payload=payload or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

async def enqueue_job(
    db: AsyncSession,
    job_type: str,
    payload: Dict[str, Any],
    project_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    run_after: Optional[datetime] = None,
) -> Job:
    """Enqueues a new asynchronous background job."""
    job = Job(
        project_id=project_id,
        job_type=job_type,
        payload=payload,
        status="queued",
        attempts=0,
        idempotency_key=idempotency_key,
        run_after=run_after or datetime.now(timezone.utc),
        progress={"percent": 0, "stage": "queued"},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

# Simple sample handler for testing Phase 0 toy job
@register_handler("toy_job")
async def handle_toy_job(db: AsyncSession, job: Job):
    await emit_job_event(db, job.id, "started", "Toy job started execution")
    await asyncio.sleep(0.5)
    await emit_job_event(db, job.id, "processing", "Processing toy payload", {"step": 1})
    await asyncio.sleep(0.5)
    await emit_job_event(db, job.id, "completed", "Toy job completed successfully")
    return {"status": "success", "echo": job.payload}

@register_handler("notion_sync_push")
async def handle_notion_sync_push(db: AsyncSession, job: Job):
    from app.notion.push import push_all_pending, push_entity_to_notion
    project_id = job.project_id or job.payload.get("project_id")
    await emit_job_event(db, job.id, "starting", f"Starting Notion push sync for project {project_id}")
    
    entity_type = job.payload.get("entity_type")
    entity_id = job.payload.get("entity_id")
    
    if entity_type and entity_id:
        res = await push_entity_to_notion(db, project_id, entity_type, entity_id)
        await emit_job_event(db, job.id, "completed", f"Pushed {entity_type}/{entity_id} to Notion")
        return res
    else:
        res = await push_all_pending(db, project_id)
        await emit_job_event(db, job.id, "completed", f"Pushed {res['pushed_count']} records to Notion")
        return res

@register_handler("notion_sync_poll")
async def handle_notion_sync_poll(db: AsyncSession, job: Job):
    from app.notion.poll import poll_all_databases
    project_id = job.project_id or job.payload.get("project_id")
    await emit_job_event(db, job.id, "polling", f"Polling Notion databases for project {project_id}")
    res = await poll_all_databases(db, project_id)
    await emit_job_event(db, job.id, "completed", f"Poll completed: {res['total_updated']} updated, {res['total_conflicts']} conflicts")
    return res

@register_handler("impact_analysis")
async def handle_impact_analysis(db: AsyncSession, job: Job):
    from app.api.v1.impact import analyze_impact, ImpactAnalyzeRequest
    project_id = job.project_id or job.payload.get("project_id")
    decision_id = job.payload.get("decision_id")
    scenario = job.payload.get("scenario", "actual")
    await emit_job_event(db, job.id, "starting", f"Analyzing change impact for decision {decision_id}")
    req = ImpactAnalyzeRequest(project_id=project_id, decision_id=decision_id, scenario=scenario)
    res = await analyze_impact(req, db=db)
    await emit_job_event(db, job.id, "completed", f"Impact analysis identified {res.total_affected} affected items")
    return {"status": "success", "total_affected": res.total_affected, "summary": res.summary}

async def process_next_job(worker_id: str = "worker-1", job_id: Optional[str] = None, db: Optional[AsyncSession] = None) -> bool:
    """Claims and executes the next eligible job from the queue (or a specific job_id)."""
    if db is not None:
        return await _execute_job_in_session(db, worker_id, job_id)
    async with AsyncSessionLocal() as session:
        return await _execute_job_in_session(session, worker_id, job_id)

async def _execute_job_in_session(session: AsyncSession, worker_id: str, job_id: Optional[str]) -> bool:
    now = datetime.now(timezone.utc)
    stmt = select(Job).where(Job.status == "queued", Job.run_after <= now)
    if job_id:
        stmt = stmt.where(Job.id == job_id)
    else:
        stmt = stmt.order_by(Job.run_after.asc())
    stmt = stmt.limit(1)
    
    # Postgres supports skip_locked; on SQLite fallback to normal lock
    if "postgresql" in str(engine.url):
        stmt = stmt.with_for_update(skip_locked=True)
        
    res = await session.execute(stmt)
    job = res.scalars().first()
    if not job:
        return False

    # Claim the job
    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = now
    job.attempts += 1
    await session.commit()
    await session.refresh(job)

    handler = HANDLERS.get(job.job_type)
    if not handler:
        job.status = "failed"
        job.result = {"error": f"No handler registered for job type: {job.job_type}"}
        await session.commit()
        return True

    try:
        result = await handler(session, job)
        job.status = "succeeded"
        job.result = result
        job.progress = {"percent": 100, "stage": "completed"}
        await session.commit()
    except Exception as exc:
        logger.error("Job execution failed", job_id=job.id, error=str(exc))
        # Retry with exponential backoff and jitter
        if job.attempts < 3:
            jitter = random.uniform(1.0, 3.0)
            backoff_seconds = (2 ** job.attempts) * 2 + jitter
            job.status = "queued"
            job.run_after = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            job.progress = {"percent": 0, "stage": f"retrying (attempt {job.attempts}/3)"}
        else:
            job.status = "failed"
            job.result = {"error": str(exc), "traceback": traceback.format_exc()}
        await session.commit()

    return True

# Ensure background job handlers are imported and registered
try:
    import app.ingestion.pipeline  # noqa: F401
except ImportError:
    pass

@register_handler("extraction")
async def handle_extraction(db: AsyncSession, job: Job):
    from app.models.entities import Document
    from sqlalchemy import select
    from app.extraction.segment import run_segmentation
    from app.extraction.extract import run_extraction
    from app.extraction.excerpt_validator import validate_excerpts
    from app.extraction.resolvers import resolve_owner, resolve_date
    from app.extraction.entity_link import link_entity
    from app.extraction.proposal_builder import build_proposals

    document_id = job.payload.get("document_id")
    await emit_job_event(db, job.id, "starting", f"Starting extraction for doc {document_id}")

    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc or not doc.content_text:
        return {"error": "document text missing or doc not found"}

    text = doc.content_text
    
    await emit_job_event(db, job.id, "segmenting", "Segmenting document text")
    seg_res = await run_segmentation(text)
    
    await emit_job_event(db, job.id, "extracting", "Extracting schema entities")
    ext_res = await run_extraction(doc.id, doc.doc_type, text)
    
    ext_res = validate_excerpts(ext_res, text)
    
    linked_entities = {}
    for d in ext_res.decisions:
        link_id, needs_att = await link_entity(db, doc.project_id, "decision", d.code, d.statement)
        linked_entities[f"decision_{d.code}"] = (link_id, needs_att)
    for t in ext_res.tasks:
        link_id, needs_att = await link_entity(db, doc.project_id, "task", t.code, t.title)
        linked_entities[f"task_{t.code}"] = (link_id, needs_att)
    for e in ext_res.experiments:
        link_id, needs_att = await link_entity(db, doc.project_id, "experiment", e.code, e.hypothesis or "")
        linked_entities[f"experiment_{e.code}"] = (link_id, needs_att)
        
    await emit_job_event(db, job.id, "building_proposals", "Building proposals")
    proposals = build_proposals(doc.project_id, ext_res, linked_entities)
    
    db.add_all(proposals)
    
    doc.pipeline_status = "extracted"
    await db.commit()
    
    await emit_job_event(db, job.id, "completed", f"Extraction completed. Generated {len(proposals)} proposals.")
    return {"proposals_count": len(proposals)}

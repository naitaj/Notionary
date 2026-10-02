import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, AsyncSessionLocal
from app.models.entities import Job, JobEvent
from app.schemas.contracts import JobCreateRequest, JobResponse, JobEventResponse
from app.core.errors import ProblemException
from app.workers.runner import enqueue_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post("", response_model=JobResponse)
async def create_job(request: JobCreateRequest, db: AsyncSession = Depends(get_db)):
    job = await enqueue_job(
        db=db,
        job_type=request.job_type,
        payload=request.payload,
        project_id=request.project_id,
        idempotency_key=request.idempotency_key,
    )
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress or {},
        result=job.result,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )

@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    query = select(Job).where(Job.id == job_id)
    res = await db.execute(query)
    job = res.scalars().first()
    if not job:
        raise ProblemException(
            status=404,
            title="Job Not Found",
            detail=f"Job with ID '{job_id}' was not found.",
        )
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress or {},
        result=job.result,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )

@router.get("/{job_id}/events")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) progress feed for long-running jobs."""
    async def event_generator():
        last_id = 0
        terminal_states = {"succeeded", "failed"}
        
        while True:
            async with AsyncSessionLocal() as session:
                # Fetch new events
                stmt = (
                    select(JobEvent)
                    .where(JobEvent.job_id == job_id, JobEvent.id > last_id)
                    .order_by(JobEvent.id.asc())
                )
                res = await session.execute(stmt)
                events = res.scalars().all()
                for ev in events:
                    last_id = ev.id
                    payload = json.dumps({
                        "id": ev.id,
                        "stage": ev.stage,
                        "message": ev.message,
                        "payload": ev.payload,
                    })
                    yield f"data: {payload}\n\n"

                # Check job completion
                job_res = await session.execute(select(Job).where(Job.id == job_id))
                job = job_res.scalars().first()
                if job and job.status in terminal_states:
                    final_payload = json.dumps({
                        "job_id": job.id,
                        "status": job.status,
                        "result": job.result,
                    })
                    yield f"event: complete\ndata: {final_payload}\n\n"
                    break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

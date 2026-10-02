import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.core.auth import UserScope
from app.ai.providers.factory import get_llm_provider, get_embedding_provider
from app.schemas.contracts import ExtractionResult
from workers.runner import enqueue_job, process_next_job
from app.models.entities import Job, JobEvent
from sqlalchemy import select

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_database_init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert data["project"] == "Notionary"

@pytest.mark.asyncio
async def test_user_scopes_permissions():
    owner_scope = UserScope(user_id="u1", project_id="p1", role="owner", team_ids=["team_core"])
    guest_scope = UserScope(user_id="u2", project_id="p1", role="guest", team_ids=[])

    assert owner_scope.can_view("project") is True
    assert owner_scope.can_view("team", "team_core") is True
    assert guest_scope.can_view("project") is True
    # Security rule: guest can NEVER see team-scoped artifacts
    assert guest_scope.can_view("team", "team_core") is False

@pytest.mark.asyncio
async def test_providers():
    llm = get_llm_provider()
    ans = await llm.complete("Why was Model B chosen?")
    assert len(ans) > 10

    # Structured contract test
    extracted = await llm.complete_structured("Dummy prompt", ExtractionResult)
    assert extracted.schema_version == "1.0.0"
    assert len(extracted.decisions) > 0

    embedder = get_embedding_provider()
    assert embedder.dimension == 384
    vec = await embedder.embed_text("MobileNetV3 on-device inference")
    assert len(vec) == 384

@pytest.mark.asyncio
async def test_job_queue_and_events():
    async with AsyncSessionLocal() as session:
        job = await enqueue_job(
            db=session,
            job_type="toy_job",
            payload={"message": "Phase 0 job queue validation"},
            project_id="test_proj",
        )
        assert job.status == "queued"
        job_id = job.id

    # Run the worker to process the queued job
    did_process = await process_next_job(worker_id="test-worker", job_id=job_id)
    assert did_process is True

    # Verify job status and generated events
    async with AsyncSessionLocal() as session:
        j = await session.get(Job, job_id)
        assert j.status == "succeeded"
        assert j.result["status"] == "success"

        events_res = await session.execute(
            select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id.asc())
        )
        events = events_res.scalars().all()
        assert len(events) >= 3
        stages = [e.stage for e in events]
        assert "started" in stages
        assert "completed" in stages

@pytest.mark.asyncio
async def test_rfc7807_error_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Non-existent job
        res = await ac.get("/api/v1/jobs/non-existent-job-uuid-1234")
        assert res.status_code == 404
        assert res.headers.get("Content-Type") == "application/problem+json"
        data = res.json()
        assert data["title"] == "Job Not Found"
        assert "detail" in data

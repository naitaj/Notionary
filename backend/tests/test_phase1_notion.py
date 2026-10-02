import pytest
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import (
    Project, Decision, Task, NotionDatabase, NotionConflict, Job
)
from app.notion.client import NotionClient, NotionRateLimiter
from app.notion.bootstrap import bootstrap_workspace
from app.notion.push import push_entity_to_notion, push_all_pending
from app.notion.poll import poll_notion_database, poll_all_databases
from app.notion.conflicts import list_conflicts, resolve_conflict
from app.notion.property_maps import to_title, to_rich_text
from sqlalchemy import select

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_notion_rate_limiter():
    limiter = NotionRateLimiter(rate_per_second=10.0, capacity=3.0)
    start = asyncio.get_event_loop().time()
    for _ in range(5):
        await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    # 5 acquisitions at 10/s with 3 capacity takes ~0.2s
    assert elapsed >= 0.15

@pytest.mark.asyncio
async def test_connect_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a test project
        async with AsyncSessionLocal() as session:
            p = Project(name="Notion Test Project")
            session.add(p)
            await session.commit()
            project_id = p.id

        # Connect
        res = await ac.post("/api/v1/notion/connect", json={
            "project_id": project_id,
            "parent_page_id": "test-notion-parent-1234",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "connected"
        assert data["parent_page_id"] == "test-notion-parent-1234"

@pytest.mark.asyncio
async def test_idempotent_bootstrap():
    client = NotionClient()
    async with AsyncSessionLocal() as session:
        p = Project(name="Bootstrap Test Project")
        session.add(p)
        await session.commit()
        project_id = p.id

        # Pass 1: Initial Bootstrap
        dbs1 = await bootstrap_workspace(session, project_id, "root-page-id", client=client)
        assert len(dbs1) == 11
        assert "decisions" in dbs1
        assert "tasks" in dbs1

        # Check DB rows
        stmt = select(NotionDatabase).where(NotionDatabase.project_id == project_id)
        res = await session.execute(stmt)
        records_pass1 = res.scalars().all()
        assert len(records_pass1) == 11

        # Pass 2: Re-bootstrap must be idempotent (no duplicates)
        dbs2 = await bootstrap_workspace(session, project_id, "root-page-id", client=client)
        assert len(dbs2) == 11
        
        res = await session.execute(stmt)
        records_pass2 = res.scalars().all()
        assert len(records_pass2) == 11  # Count does not double!

@pytest.mark.asyncio
async def test_push_with_pos_id_dedup():
    client = NotionClient()
    async with AsyncSessionLocal() as session:
        p = Project(name="Push Test Project")
        session.add(p)
        await session.flush()
        project_id = p.id

        # Bootstrap
        await bootstrap_workspace(session, project_id, "parent-page", client=client)

        # Create local decision
        dec = Decision(
            project_id=project_id,
            code="D-99",
            statement="Test Edge Decision for Notion Sync",
            rationale="Verifying POS_ID lookup",
            status="active",
            version=1,
        )
        session.add(dec)
        await session.commit()
        dec_id = dec.id

        # Push to Notion (Call 1)
        res1 = await push_entity_to_notion(session, project_id, "decisions", dec_id, client=client)
        assert res1["status"] == "synced"
        page_id_1 = res1["page_id"]
        assert page_id_1 is not None

        # Verify page stored in mock client
        assert page_id_1 in client.mock_pages
        assert "POS_ID" in client.mock_pages[page_id_1]["properties"]

        # Push to Notion (Call 2 - retry): Must NOT create duplicate page!
        dec.notion_page_id = None  # Simulate lost local reference on client retry
        await session.commit()

        res2 = await push_entity_to_notion(session, project_id, "decisions", dec_id, client=client)
        page_id_2 = res2["page_id"]
        # POS_ID lookup found page_id_1, avoided duplicate!
        assert page_id_2 == page_id_1

@pytest.mark.asyncio
async def test_self_trigger_prevention():
    client = NotionClient()
    async with AsyncSessionLocal() as session:
        p = Project(name="Self Trigger Test Project")
        session.add(p)
        await session.flush()
        project_id = p.id
        await bootstrap_workspace(session, project_id, "parent-page", client=client)

        dec = Decision(
            project_id=project_id,
            code="D-101",
            statement="Self Trigger Baseline",
            status="active",
        )
        session.add(dec)
        await session.commit()

        # Push
        await push_entity_to_notion(session, project_id, "decisions", dec.id, client=client)

        # Immediately poll: since app just wrote and hashes match, updated_count must be 0!
        poll_res = await poll_notion_database(session, project_id, "decisions", client=client)
        assert poll_res["updated_count"] == 0
        assert poll_res["conflicts"] == 0

@pytest.mark.asyncio
async def test_notion_human_edit_version_bump_and_impact_trigger():
    client = NotionClient()
    async with AsyncSessionLocal() as session:
        p = Project(name="Hero Loop Test Project")
        session.add(p)
        await session.flush()
        project_id = p.id
        await bootstrap_workspace(session, project_id, "parent-page", client=client)

        dec = Decision(
            project_id=project_id,
            code="D-17",
            statement="Adopt MobileNetV3-Small",
            rationale="Initial edge selection",
            status="active",
            version=1,
        )
        session.add(dec)
        await session.commit()

        # 1. App pushes initial Decision to Notion
        push_res = await push_entity_to_notion(session, project_id, "decisions", dec.id, client=client)
        page_id = push_res["page_id"]

        # 2. Simulate human in Notion editing page: Changing statement to Model C
        human_edited_time = "2026-10-03T10:00:00Z"
        client.mock_pages[page_id]["properties"]["Decision"] = {
            "title": to_title("[D-17] Adopt MobileNetV3-Large for Enhanced Field Precision")
        }
        client.mock_pages[page_id]["properties"]["Rationale"] = {
            "rich_text": to_rich_text("Field trial EXP-09 showed Model B accuracy drop, switching to Model C.")
        }
        client.mock_pages[page_id]["last_edited_time"] = human_edited_time

        # 3. Poll Notion
        poll_res = await poll_notion_database(session, project_id, "decisions", client=client)
        assert poll_res["updated_count"] == 1

        # 4. Verify Decision version 1 is closed (effective_to is set)
        await session.refresh(dec)
        assert dec.status == "superseded"
        assert dec.effective_to is not None

        # 5. Verify Decision version 2 is active
        v2_res = await session.execute(
            select(Decision).where(Decision.project_id == project_id, Decision.code == "D-17", Decision.version == 2)
        )
        v2 = v2_res.scalars().first()
        assert v2 is not None
        assert "Adopt MobileNetV3-Large" in v2.statement
        assert v2.effective_to is None
        assert v2.supersedes_id == dec.id

        # 6. Verify impact_analysis job was enqueued automatically!
        job_res = await session.execute(
            select(Job).where(Job.project_id == project_id, Job.job_type == "impact_analysis")
        )
        impact_job = job_res.scalars().first()
        assert impact_job is not None
        assert impact_job.payload["decision_id"] == v2.id

@pytest.mark.asyncio
async def test_conflict_detection_and_resolution():
    client = NotionClient()
    async with AsyncSessionLocal() as session:
        p = Project(name="Conflict Test Project")
        session.add(p)
        await session.flush()
        project_id = p.id
        await bootstrap_workspace(session, project_id, "parent-page", client=client)

        task = Task(
            project_id=project_id,
            code="T-200",
            title="Local Task",
            status="todo",
        )
        session.add(task)
        await session.commit()

        # Push to Notion
        push_res = await push_entity_to_notion(session, project_id, "tasks", task.id, client=client)
        page_id = push_res["page_id"]

        # Simulate simultaneous edits:
        # App side edits task
        task.title = "Local Task Updated in App"
        task.local_dirty = True
        await session.commit()

        # Notion side edits task
        client.mock_pages[page_id]["properties"]["Task"] = {"title": to_title("[T-200] Task Edited in Notion")}
        client.mock_pages[page_id]["last_edited_time"] = "2026-10-03T11:00:00Z"

        # Poll should detect conflict
        poll_res = await poll_notion_database(session, project_id, "tasks", client=client)
        assert poll_res["conflicts"] == 1

        conflicts = await list_conflicts(session, project_id)
        assert len(conflicts) >= 1
        c = conflicts[0]
        assert c.entity_id == task.id
        assert c.status == "open"

        # Resolve conflict: Notion wins
        res = await resolve_conflict(session, c.id, resolution_choice="notion_wins")
        assert res["status"] == "resolved"
        assert res["choice"] == "notion_wins"

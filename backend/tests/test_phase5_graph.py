from uuid import uuid4
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import Decision, Task, Experiment, Claim, Edge, Project
from app.graph.traversal import traverse_graph

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_graph_traversal_bfs_with_cycle_guard():
    """
    Plan §5.1: Graph traversal with cycle detection.
    Seed a 3-node cycle (D1 → D2 → D3 → D1) and verify BFS terminates,
    finds exactly 3 nodes, and 3 edges without infinite loop.
    """
    pid = str(uuid4())
    d1_id, d2_id, d3_id = str(uuid4()), str(uuid4()), str(uuid4())
    e1_id, e2_id, e3_id = str(uuid4()), str(uuid4()), str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add_all([
            Decision(id=d1_id, project_id=pid, code="D-CYC1", statement="Cycle Node 1"),
            Decision(id=d2_id, project_id=pid, code="D-CYC2", statement="Cycle Node 2"),
            Decision(id=d3_id, project_id=pid, code="D-CYC3", statement="Cycle Node 3"),
        ])
        await db.flush()

        db.add_all([
            Edge(id=e1_id, project_id=pid, from_id=d1_id, from_type="decision", to_id=d2_id, to_type="decision", edge_type="supports"),
            Edge(id=e2_id, project_id=pid, from_id=d2_id, from_type="decision", to_id=d3_id, to_type="decision", edge_type="supports"),
            Edge(id=e3_id, project_id=pid, from_id=d3_id, from_type="decision", to_id=d1_id, to_type="decision", edge_type="supports"),
        ])
        await db.commit()

        nodes, edges = await traverse_graph(db, pid, start_id=d1_id, direction="both", max_depth=4)

        assert len(nodes) == 3, f"Expected 3 nodes in cycle, got {len(nodes)}"
        assert len(edges) == 3, f"Expected 3 edges in cycle, got {len(edges)}"

@pytest.mark.asyncio
async def test_edge_crud_and_review_lifecycle():
    """
    Plan §5.2: Edge CRUD + review lifecycle.
    Create an AI-inferred edge (auto-unreviewed), approve it, then retire it.
    """
    pid = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/edges", json={
            "project_id": pid,
            "from_type": "decision",
            "from_id": str(uuid4()),
            "to_type": "task",
            "to_id": str(uuid4()),
            "edge_type": "resulted_in",
            "origin": "ai_inferred",
        })
        assert resp.status_code == 200
        edge = resp.json()
        assert edge["review_status"] == "unreviewed"
        edge_id = edge["id"]

        resp = await ac.post(f"/api/v1/edges/{edge_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "approved"

        resp = await ac.post(f"/api/v1/edges/{edge_id}/retire")
        assert resp.status_code == 200
        assert resp.json()["effective_to"] is not None

@pytest.mark.asyncio
async def test_subgraph_ego_network():
    """
    Plan §5.3: GET /graph/subgraph returns ego-network.
    Seed a center decision linked to a task, verify subgraph returns 2 nodes and 1 edge.
    """
    pid = str(uuid4())
    d_id = str(uuid4())
    t_id = str(uuid4())
    e_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add_all([
            Decision(id=d_id, project_id=pid, code="D-EGO", statement="Ego Center"),
            Task(id=t_id, project_id=pid, code="T-EGO", title="Ego Child Task"),
        ])
        await db.flush()

        db.add(Edge(id=e_id, project_id=pid, from_id=d_id, from_type="decision", to_id=t_id, to_type="task", edge_type="resulted_in"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/graph/subgraph?project_id={pid}&center_id={d_id}&depth=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

@pytest.mark.asyncio
async def test_decision_lineage_upstream_downstream():
    """
    Plan §5.4: Decision lineage shows upstream evidence and downstream work.
    Seed D-17 with upstream EXP-06 + CL-02 and downstream T-14.
    """
    pid = str(uuid4())
    d_id = str(uuid4())
    exp_id = str(uuid4())
    cl_id = str(uuid4())
    t_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add_all([
            Decision(id=d_id, project_id=pid, code="D-LIN", statement="Lineage Decision"),
            Experiment(id=exp_id, project_id=pid, code="EXP-LIN", hypothesis="Hypothesis"),
            Claim(id=cl_id, project_id=pid, statement="Supporting claim"),
            Task(id=t_id, project_id=pid, code="T-LIN", title="Downstream Task"),
        ])
        await db.flush()

        db.add_all([
            Edge(id=str(uuid4()), project_id=pid, from_id=exp_id, from_type="experiment", to_id=d_id, to_type="decision", edge_type="supports"),
            Edge(id=str(uuid4()), project_id=pid, from_id=cl_id, from_type="claim", to_id=d_id, to_type="decision", edge_type="supports"),
            Edge(id=str(uuid4()), project_id=pid, from_id=d_id, from_type="decision", to_id=t_id, to_type="task", edge_type="resulted_in"),
        ])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/decisions/{d_id}/lineage")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["upstream_evidence"]) >= 2, f"Expected >= 2 upstream, got {len(data['upstream_evidence'])}"
        assert len(data["downstream_work"]) >= 1, f"Expected >= 1 downstream, got {len(data['downstream_work'])}"

@pytest.mark.asyncio
async def test_task_context_why_chain():
    """
    Plan §5.5: Task context shows "Why does this exist?" with origin chain.
    """
    pid = str(uuid4())
    d_id = str(uuid4())
    t_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add_all([
            Decision(id=d_id, project_id=pid, code="D-WHY", statement="Why Decision"),
            Task(id=t_id, project_id=pid, code="T-WHY", title="Why Task", origin_decision_id=d_id),
        ])
        await db.flush()

        db.add(Edge(id=str(uuid4()), project_id=pid, from_id=d_id, from_type="decision", to_id=t_id, to_type="task", edge_type="resulted_in"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/tasks/{t_id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["origin_decision"]["id"] == d_id
        assert "chain" in data
        assert len(data["chain"]) >= 1

@pytest.mark.asyncio
async def test_as_of_time_travel():
    """
    Plan §5.7: Time-travel lineage via as_of parameter.
    Create an edge with effective_from far in the future, verify as_of=past excludes it.
    """
    pid = str(uuid4())
    d_id = str(uuid4())
    t_id = str(uuid4())
    e_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add_all([
            Decision(id=d_id, project_id=pid, code="D-TT", statement="Time Travel Dec"),
            Task(id=t_id, project_id=pid, code="T-TT", title="Time Travel Task"),
        ])
        await db.flush()

        future_dt = datetime(2100, 1, 1, tzinfo=timezone.utc)
        db.add(Edge(
            id=e_id, project_id=pid,
            from_id=d_id, from_type="decision",
            to_id=t_id, to_type="task",
            edge_type="resulted_in",
            effective_from=future_dt,
        ))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/decisions/{d_id}/lineage?as_of=2020-01-01T00:00:00Z")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["downstream_work"]) == 0, "Future edge should be excluded by as_of=2020"

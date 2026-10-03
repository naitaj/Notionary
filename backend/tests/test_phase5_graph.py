import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.entities import Decision, Task, Experiment, Claim, Edge
from app.graph.traversal import traverse_graph

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_graph_traversal_bfs_with_cycle_guard():
    async with AsyncSessionLocal() as db_session:
        pid = "proj_test_cycle"
        
        n1 = Decision(id="d1", project_id=pid, code="D-1", statement="Node 1")
        n2 = Decision(id="d2", project_id=pid, code="D-2", statement="Node 2")
        n3 = Decision(id="d3", project_id=pid, code="D-3", statement="Node 3")
        
        db_session.add_all([n1, n2, n3])
        await db_session.flush()
        
        e1 = Edge(id="e1", project_id=pid, from_id="d1", from_type="decision", to_id="d2", to_type="decision", edge_type="supports")
        e2 = Edge(id="e2", project_id=pid, from_id="d2", from_type="decision", to_id="d3", to_type="decision", edge_type="supports")
        e3 = Edge(id="e3", project_id=pid, from_id="d3", from_type="decision", to_id="d1", to_type="decision", edge_type="supports")
        
        db_session.add_all([e1, e2, e3])
        await db_session.commit()
        
        nodes, edges = await traverse_graph(db_session, pid, start_id="d1", direction="both", max_depth=4)
        
        assert len(nodes) == 3
        assert len(edges) == 3

@pytest.mark.asyncio
async def test_edge_crud_and_review_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        pid = "proj_crud"
        
        resp = await async_client.post("/api/v1/edges", json={
            "project_id": pid,
            "from_type": "decision",
            "from_id": "n1",
            "to_type": "task",
            "to_id": "n2",
            "edge_type": "resulted_in",
            "origin": "ai_inferred"
        })
        assert resp.status_code == 200
        edge = resp.json()
        assert edge["review_status"] == "unreviewed"
        edge_id = edge["id"]
        
        resp = await async_client.post(f"/api/v1/edges/{edge_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "approved"
        
        resp = await async_client.post(f"/api/v1/edges/{edge_id}/retire")
        assert resp.status_code == 200
        assert resp.json()["effective_to"] is not None

@pytest.mark.asyncio
async def test_subgraph_ego_network():
    async with AsyncSessionLocal() as db_session:
        pid = "proj_ego"
        n1 = Decision(id="ego_d1", project_id=pid, code="D-EGO", statement="Center")
        n2 = Task(id="ego_t1", project_id=pid, code="T-EGO", title="Child")
        db_session.add_all([n1, n2])
        await db_session.flush()
        
        e1 = Edge(id="ego_e1", project_id=pid, from_id="ego_d1", from_type="decision", to_id="ego_t1", to_type="task", edge_type="resulted_in")
        db_session.add(e1)
        await db_session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        resp = await async_client.get(f"/api/v1/graph/subgraph?project_id={pid}&center_id=ego_d1&depth=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

@pytest.mark.asyncio
async def test_decision_lineage_upstream_downstream():
    async with AsyncSessionLocal() as db_session:
        pid = "proj_lineage"
        d1 = Decision(id="d_test", project_id=pid, code="D-TEST", statement="Test Dec")
        e1 = Experiment(id="e_test", project_id=pid, code="EXP-TEST", hypothesis="Hyp")
        c1 = Claim(id="c_test", project_id=pid, statement="Claim")
        t1 = Task(id="t_test", project_id=pid, code="T-TEST", title="Task")
        
        db_session.add_all([d1, e1, c1, t1])
        await db_session.flush()
        
        edge1 = Edge(id="edge_up1", project_id=pid, from_id="e_test", from_type="experiment", to_id="d_test", to_type="decision", edge_type="supports")
        edge2 = Edge(id="edge_up2", project_id=pid, from_id="c_test", from_type="claim", to_id="d_test", to_type="decision", edge_type="supports")
        edge3 = Edge(id="edge_down", project_id=pid, from_id="d_test", from_type="decision", to_id="t_test", to_type="task", edge_type="resulted_in")
        
        db_session.add_all([edge1, edge2, edge3])
        await db_session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        resp = await async_client.get(f"/api/v1/decisions/d_test/lineage")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["upstream_evidence"]) == 2
        assert len(data["downstream_work"]) == 1

@pytest.mark.asyncio
async def test_task_context_why_chain():
    async with AsyncSessionLocal() as db_session:
        pid = "proj_taskctx"
        d1 = Decision(id="d_ctx", project_id=pid, code="D-CTX", statement="Ctx Dec")
        t1 = Task(id="t_ctx", project_id=pid, code="T-CTX", title="Ctx Task", origin_decision_id="d_ctx")
        
        db_session.add_all([d1, t1])
        await db_session.flush()
        
        edge1 = Edge(id="edge_ctx", project_id=pid, from_id="d_ctx", from_type="decision", to_id="t_ctx", to_type="task", edge_type="resulted_in")
        db_session.add(edge1)
        await db_session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        resp = await async_client.get(f"/api/v1/tasks/t_ctx/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["origin_decision"]["id"] == "d_ctx"
        assert "chain" in data

@pytest.mark.asyncio
async def test_as_of_time_travel():
    async with AsyncSessionLocal() as db_session:
        pid = "proj_time"
        d1 = Decision(id="d_time", project_id=pid, code="D-TIME", statement="Time")
        t1 = Task(id="t_time", project_id=pid, code="T-TIME", title="Time Task")
        
        db_session.add_all([d1, t1])
        await db_session.flush()
        
        edge1 = Edge(id="edge_time", project_id=pid, from_id="d_time", from_type="decision", to_id="t_time", to_type="task", edge_type="resulted_in")
        db_session.add(edge1)
        await db_session.commit()
        
        await db_session.execute(text("UPDATE edges SET effective_from = '2100-01-01 00:00:00' WHERE id = 'edge_time'"))
        await db_session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        resp = await async_client.get(f"/api/v1/decisions/d_time/lineage?as_of=2020-01-01T00:00:00Z")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["downstream_work"]) == 0

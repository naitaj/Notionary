import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from sqlalchemy import select
from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import Project, Claim, Contradiction, Document, Decision, Edge, DatasetAlias
from app.contradictions.normalization import get_normalized_claim_keys

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

async def setup_data(db):
    proj_id = str(uuid.uuid4())
    proj = Project(id=proj_id, name="Phase 6 Test")
    db.add(proj)
    
    # Dataset Aliases
    aliases = [
        DatasetAlias(id=str(uuid.uuid4()), project_id=proj_id, kind="subject", canonical="MobileNetV3", alias="model b"),
        DatasetAlias(id=str(uuid.uuid4()), project_id=proj_id, kind="metric", canonical="accuracy", alias="acc")
    ]
    db.add_all(aliases)
    
    # Claims
    c1 = Claim(
        id=str(uuid.uuid4()), project_id=proj_id, statement="EXP-06 benchmark accuracy is 91.2%",
        subject="MobileNetV3", metric="accuracy", value=91.2, condition="benchmark", direction="better"
    )
    c2 = Claim(
        id=str(uuid.uuid4()), project_id=proj_id, statement="EXP-09 rural field test showed degraded accuracy of 76.4%",
        subject="model b", metric="acc", value=76.4, condition="harsh field sunlight", direction="worse"
    )
    c3 = Claim(
        id=str(uuid.uuid4()), project_id=proj_id, statement="ResNet-18 achieves 88.5% accuracy.",
        subject="ResNet-18", metric="accuracy", value=88.5, condition="benchmark", direction="better"
    )
    
    c4 = Claim(
        id=str(uuid.uuid4()), project_id=proj_id, statement="Different models compatible contexts.",
        source_excerpt="Context A"
    )
    c5 = Claim(
        id=str(uuid.uuid4()), project_id=proj_id, statement="Needs_context=true",
        source_excerpt="Context B"
    )
    c4.embedding = [0.1] * 384
    c5.embedding = [0.1] * 384
    
    db.add_all([c1, c2, c3, c4, c5])
    
    doc1 = Document(id=str(uuid.uuid4()), project_id=proj_id, title="DOC-05", content_text="Selected Edge Architecture: ResNet-18")
    doc2 = Document(id=str(uuid.uuid4()), project_id=proj_id, title="DOC-06", content_text="MobileNet is great", updated_at=datetime(2020, 1, 1))
    
    dec1 = Decision(id=str(uuid.uuid4()), project_id=proj_id, code="D-1", statement="Adopt MobileNetV3-Small", status="active")
    dec2 = Decision(id=str(uuid.uuid4()), project_id=proj_id, code="D-2", statement="Superseded Dec", status="active", updated_at=datetime(2021, 1, 1))
    
    db.add_all([doc1, doc2, dec1, dec2])
    
    e1 = Edge(id=str(uuid.uuid4()), project_id=proj_id, from_type="document", from_id=doc2.id, to_type="decision", to_id=dec2.id, edge_type="references")
    db.add(e1)
    
    await db.commit()
    return proj_id, c1.id, c2.id, c3.id, c4.id, c5.id, doc1.id, doc2.id

@pytest.mark.asyncio
async def test_normalization_and_rule_detection():
    async with AsyncSessionLocal() as db:
        proj_id, c1_id, c2_id, c3_id, c4_id, c5_id, d1_id, d2_id = await setup_data(db)
        
        from app.contradictions.rules import check_rule_contradiction
        from app.ingestion.csv_mapper import ensure_dataset_aliases
        
        alias_lookup = await ensure_dataset_aliases(db, proj_id)
        
        c1 = (await db.execute(select(Claim).where(Claim.id == c1_id))).scalars().first()
        c2 = (await db.execute(select(Claim).where(Claim.id == c2_id))).scalars().first()
        c3 = (await db.execute(select(Claim).where(Claim.id == c3_id))).scalars().first()
        
        res = check_rule_contradiction(c1, c2, alias_lookup)
        assert res is not None
        assert res.is_contradiction
        
        res_neg = check_rule_contradiction(c1, c3, alias_lookup)
        assert res_neg is None

@pytest.mark.asyncio
async def test_scanner_end_to_end():
    async with AsyncSessionLocal() as db:
        proj_id, *_ = await setup_data(db)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/contradictions/scan?project_id={proj_id}&sync=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["contradictions_found"] >= 1
        assert data["result"]["stale_docs_found"] >= 1

@pytest.mark.asyncio
async def test_resolve_contradiction():
    async with AsyncSessionLocal() as db:
        proj_id, *_ = await setup_data(db)
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(f"/api/v1/contradictions/scan?project_id={proj_id}&sync=true")
        
        resp = await ac.get(f"/api/v1/contradictions?project_id={proj_id}")
        assert resp.status_code == 200
        contradictions = resp.json()
        assert len(contradictions) >= 1
        c_id = contradictions[0]["id"]
        
        resp2 = await ac.post(f"/api/v1/contradictions/{c_id}/resolve", json={
            "status": "confirmed",
            "resolution_notes": "Yes it is.",
            "create_task": True,
            "task_title": "Fix this"
        })
        assert resp2.status_code == 200
        
    async with AsyncSessionLocal() as db:
        edges = (await db.execute(select(Edge).where(Edge.edge_type == "contradicts"))).scalars().all()
        assert len(edges) >= 1
        
        from app.models.entities import Task
        tasks = (await db.execute(select(Task).where(Task.project_id == proj_id))).scalars().all()
        assert len(tasks) >= 1

@pytest.mark.asyncio
async def test_eval_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/contradictions/eval/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["precision"] == 1.0
        assert data["false_positive_rate"] == 0.0

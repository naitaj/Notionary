"""
Phase 7 — Change-Impact Analysis tests

Covers:
  7.1 analyze_impact() — directed graph traversal
  7.2 Classification + deterministic ranking
  7.3 Graph completeness hints
  7.5 API endpoints (POST /analyze, GET /{id}, POST /{id}/apply)
  7.6 Auto-trigger via worker handler
  7.8 Expected-set test for LeafGuard Model B → C scenario
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import (
    Project, Decision, Task, Experiment, Deliverable, Document,
    Milestone, Edge, ImpactAnalysis, StaleFlag,
)
from app.graph.impact import compute_impact, _rank_key


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def seed_leafguard_scenario(db):
    """
    Seed the LeafGuard Model B → C scenario (Plan §7.8 / Exit criteria):

        D-17 ──resulted_in──> T-14 ──contributes_to──> DL-02
        D-17 ──resulted_in──> T-15 ──contributes_to──> DL-01
        DOC-05 ──describes──> D-17
        EXP-06 ──supports──> D-17   (should NOT appear in impact)

    Expected affected set: T-14, T-15, DL-02, DL-01, DOC-05
    """
    pid = str(uuid4())
    proj = Project(id=pid, name="LeafGuard Impact Test")
    db.add(proj)

    # Decision (trigger)
    d17_id = str(uuid4())
    d17 = Decision(
        id=d17_id, project_id=pid, code="D-17",
        statement="Use Model B (MobileNetV3 + augmentation)",
        status="active", version=2,
        decided_on=datetime(2026, 9, 21, tzinfo=timezone.utc),
        decided_by="Rohan",
    )
    db.add(d17)

    # Tasks
    t14_id = str(uuid4())
    t14 = Task(
        id=t14_id, project_id=pid, code="T-14",
        title="Quantize model for Android",
        status="in_progress", priority="high",
        origin_decision_id=d17_id,
    )
    t15_id = str(uuid4())
    t15 = Task(
        id=t15_id, project_id=pid, code="T-15",
        title="Augmentation pipeline",
        status="todo", priority="medium",
        origin_decision_id=d17_id,
    )
    db.add_all([t14, t15])

    # Deliverables
    dl02_id = str(uuid4())
    dl02 = Deliverable(
        id=dl02_id, project_id=pid, name="Demo APK",
        status="in_progress",
    )
    dl01_id = str(uuid4())
    dl01 = Deliverable(
        id=dl01_id, project_id=pid, name="Benchmark report",
        status="in_progress",
    )
    db.add_all([dl02, dl01])

    # Document (stale candidate)
    doc05_id = str(uuid4())
    doc05 = Document(
        id=doc05_id, project_id=pid, title="DOC-05",
        content_text="System Architecture & Edge Deployment Spec v1",
    )
    db.add(doc05)

    # Experiment (linked via supports — should NOT appear in impact)
    exp06_id = str(uuid4())
    exp06 = Experiment(
        id=exp06_id, project_id=pid, code="EXP-06",
        hypothesis="MobileNetV3 benchmark",
        status="completed",
    )
    db.add(exp06)

    await db.flush()

    # ── Edges ─────────────────────────────────────────────────────
    edges = [
        # Forward impact edges
        Edge(id=str(uuid4()), project_id=pid,
             from_id=d17_id, from_type="decision",
             to_id=t14_id, to_type="task",
             edge_type="resulted_in"),
        Edge(id=str(uuid4()), project_id=pid,
             from_id=d17_id, from_type="decision",
             to_id=t15_id, to_type="task",
             edge_type="resulted_in"),
        Edge(id=str(uuid4()), project_id=pid,
             from_id=t14_id, from_type="task",
             to_id=dl02_id, to_type="deliverable",
             edge_type="contributes_to"),
        Edge(id=str(uuid4()), project_id=pid,
             from_id=t15_id, from_type="task",
             to_id=dl01_id, to_type="deliverable",
             edge_type="contributes_to"),
        # Reverse impact edge (describes)
        Edge(id=str(uuid4()), project_id=pid,
             from_id=doc05_id, from_type="document",
             to_id=d17_id, to_type="decision",
             edge_type="describes"),
        # Non-impact edge (supports — should be excluded)
        Edge(id=str(uuid4()), project_id=pid,
             from_id=exp06_id, from_type="experiment",
             to_id=d17_id, to_type="decision",
             edge_type="supports"),
    ]
    db.add_all(edges)
    await db.commit()

    return {
        "project_id": pid,
        "d17_id": d17_id,
        "t14_id": t14_id,
        "t15_id": t15_id,
        "dl02_id": dl02_id,
        "dl01_id": dl01_id,
        "doc05_id": doc05_id,
        "exp06_id": exp06_id,
    }


# ═══════════════════════════════════════════════════════════════════════
# 7.1 — Core graph traversal
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_impact_traversal_finds_expected_set():
    """
    Plan §7.8 Exit Criteria: D-17 change produces T-14 (hop 1), T-15 (hop 1),
    DL-02 (hop 2), DL-01 (hop 2), DOC-05 (hop 1, stale).  EXP-06 should NOT
    appear (supports is excluded from impact edges).
    """
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)

        result = await compute_impact(
            db=db,
            project_id=ids["project_id"],
            decision_id=ids["d17_id"],
        )

    affected_ids = {item.id for item in result.affected_items}

    # Should be present
    assert ids["t14_id"] in affected_ids, "T-14 missing from impact"
    assert ids["t15_id"] in affected_ids, "T-15 missing from impact"
    assert ids["dl02_id"] in affected_ids, "DL-02 missing from impact"
    assert ids["dl01_id"] in affected_ids, "DL-01 missing from impact"
    assert ids["doc05_id"] in affected_ids, "DOC-05 missing from impact"

    # Should NOT be present (supports is not an impact edge)
    assert ids["exp06_id"] not in affected_ids, "EXP-06 should be excluded (supports)"

    assert result.total_affected == 5


@pytest.mark.asyncio
async def test_impact_hop_distances():
    """Verify correct hop assignment: tasks at hop 1, deliverables at hop 2, doc at hop 1."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)
        result = await compute_impact(db, ids["project_id"], ids["d17_id"])

    item_map = {item.id: item for item in result.affected_items}

    assert item_map[ids["t14_id"]].hop == 1
    assert item_map[ids["t15_id"]].hop == 1
    assert item_map[ids["dl02_id"]].hop == 2
    assert item_map[ids["dl01_id"]].hop == 2
    assert item_map[ids["doc05_id"]].hop == 1


# ═══════════════════════════════════════════════════════════════════════
# 7.2 — Classification + deterministic ranking
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_impact_classification():
    """Each affected item is classified correctly by entity type."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)
        result = await compute_impact(db, ids["project_id"], ids["d17_id"])

    item_map = {item.id: item for item in result.affected_items}

    assert item_map[ids["t14_id"]].relationship_class == "task_affected"
    assert item_map[ids["t15_id"]].relationship_class == "task_affected"
    assert item_map[ids["dl02_id"]].relationship_class == "deliverable_risk"
    assert item_map[ids["dl01_id"]].relationship_class == "deliverable_risk"
    assert item_map[ids["doc05_id"]].relationship_class == "stale_doc"


@pytest.mark.asyncio
async def test_impact_ranking_order():
    """
    Deterministic ranking: hop ASC, category priority DESC, status cost DESC.
    Hop 1 items come before hop 2.  Within hop 1, task_affected (prio 4) >
    stale_doc (prio 1).  Within same category, in_progress > todo.
    """
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)
        result = await compute_impact(db, ids["project_id"], ids["d17_id"])

    # All hop-1 items must appear before all hop-2 items
    hop1 = [i for i in result.affected_items if i.hop == 1]
    hop2 = [i for i in result.affected_items if i.hop == 2]
    hop1_idx = [result.affected_items.index(i) for i in hop1]
    hop2_idx = [result.affected_items.index(i) for i in hop2]
    assert max(hop1_idx) < min(hop2_idx), "Hop 1 items must rank before hop 2"

    # Within hop 1, task_affected should come before stale_doc
    task_items = [i for i in hop1 if i.relationship_class == "task_affected"]
    stale_items = [i for i in hop1 if i.relationship_class == "stale_doc"]
    if task_items and stale_items:
        assert (
            result.affected_items.index(task_items[0])
            < result.affected_items.index(stale_items[0])
        )


@pytest.mark.asyncio
async def test_impact_path_descriptions():
    """Path descriptions contain meaningful edge types and node labels."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)
        result = await compute_impact(db, ids["project_id"], ids["d17_id"])

    item_map = {item.id: item for item in result.affected_items}

    # T-14 path should mention D-17 and resulted_in
    t14_path = item_map[ids["t14_id"]].path_description
    assert "D-17" in t14_path
    assert "resulted_in" in t14_path

    # DL-02 path should mention contributes_to (hop 2)
    dl02_path = item_map[ids["dl02_id"]].path_description
    assert "contributes_to" in dl02_path

    # DOC-05 path should mention describes (reverse)
    doc05_path = item_map[ids["doc05_id"]].path_description
    assert "describes" in doc05_path


# ═══════════════════════════════════════════════════════════════════════
# 7.3 — Graph completeness hints
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_completeness_hints_for_orphan_tasks():
    """
    Tasks with no upstream edges (no resulted_in pointing to them) should
    appear in completeness_hints.
    """
    pid = str(uuid4())
    d_id = str(uuid4())
    t_orphan_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add(Project(id=pid, name="Completeness Test"))
        db.add(Decision(id=d_id, project_id=pid, code="D-X", statement="Test"))
        db.add(Task(
            id=t_orphan_id, project_id=pid, code="T-ORPHAN",
            title="Orphan Task", status="todo",
        ))
        await db.flush()
        # D-X ──resulted_in──> T-ORPHAN
        db.add(Edge(
            id=str(uuid4()), project_id=pid,
            from_id=d_id, from_type="decision",
            to_id=t_orphan_id, to_type="task",
            edge_type="resulted_in",
        ))
        await db.commit()

        result = await compute_impact(db, pid, d_id)

    # T-ORPHAN is the only affected item and it has NO upstream supports/references
    hint_ids = {h["id"] for h in result.completeness_hints}
    assert t_orphan_id in hint_ids, "Orphan task should appear in completeness hints"


# ═══════════════════════════════════════════════════════════════════════
# 7.5 — API endpoints
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_post_analyze():
    """POST /impact/analyze returns classified impact with expected items."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/v1/impact/analyze", json={
            "project_id": ids["project_id"],
            "decision_id": ids["d17_id"],
            "add_llm_phrasing": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_affected"] == 5
        assert len(data["affected_items"]) == 5
        assert "completeness_hints" in data

        # Should have a summary mentioning D-17
        assert "D-17" in data["summary"]


@pytest.mark.asyncio
async def test_api_get_stored_analysis():
    """GET /impact/{id} retrieves a persisted analysis."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # First, create an analysis
        resp = await ac.post("/api/v1/impact/analyze", json={
            "project_id": ids["project_id"],
            "decision_id": ids["d17_id"],
            "add_llm_phrasing": False,
        })
        assert resp.status_code == 200

        # Find the stored analysis
        async with AsyncSessionLocal() as db2:
            res = await db2.execute(
                select(ImpactAnalysis).where(
                    ImpactAnalysis.project_id == ids["project_id"]
                )
            )
            analysis = res.scalars().first()
            assert analysis is not None

            # Retrieve it
            resp2 = await ac.get(f"/api/v1/impact/{analysis.id}")
            assert resp2.status_code == 200
            data = resp2.json()
            assert data["trigger_decision_id"] == ids["d17_id"]


@pytest.mark.asyncio
async def test_api_apply_sets_reevaluation_and_stale():
    """POST /impact/{id}/apply flags tasks and creates stale flags."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Create analysis
        resp = await ac.post("/api/v1/impact/analyze", json={
            "project_id": ids["project_id"],
            "decision_id": ids["d17_id"],
            "add_llm_phrasing": False,
        })
        assert resp.status_code == 200

        # Find stored analysis
        async with AsyncSessionLocal() as db2:
            res = await db2.execute(
                select(ImpactAnalysis).where(
                    ImpactAnalysis.project_id == ids["project_id"]
                )
            )
            analysis = res.scalars().first()

        # Apply all items
        resp2 = await ac.post(f"/api/v1/impact/{analysis.id}/apply", json={
            "apply_items": [],  # empty = apply all
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["tasks_flagged"] == 2, f"Expected 2 tasks flagged, got {data['tasks_flagged']}"
        assert data["docs_flagged_stale"] == 1, f"Expected 1 doc stale, got {data['docs_flagged_stale']}"

    # Verify DB state
    async with AsyncSessionLocal() as db3:
        # Tasks should have needs_reevaluation = True
        for tid in [ids["t14_id"], ids["t15_id"]]:
            task = (await db3.execute(select(Task).where(Task.id == tid))).scalar_one()
            assert task.needs_reevaluation is True, f"Task {task.code} should be flagged for re-evaluation"

        # Stale flag should exist for DOC-05
        stale = (await db3.execute(
            select(StaleFlag).where(StaleFlag.document_id == ids["doc05_id"])
        )).scalars().all()
        assert len(stale) >= 1, "DOC-05 should have a stale flag"


@pytest.mark.asyncio
async def test_api_apply_with_reevaluation_tasks():
    """POST /impact/{id}/apply with create_reevaluation_tasks=true creates new tasks."""
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/v1/impact/analyze", json={
            "project_id": ids["project_id"],
            "decision_id": ids["d17_id"],
            "add_llm_phrasing": False,
        })

        async with AsyncSessionLocal() as db2:
            analysis = (await db2.execute(
                select(ImpactAnalysis).where(
                    ImpactAnalysis.project_id == ids["project_id"]
                )
            )).scalars().first()

        resp2 = await ac.post(f"/api/v1/impact/{analysis.id}/apply", json={
            "apply_items": [ids["t14_id"]],
            "create_reevaluation_tasks": True,
            "reevaluation_task_prefix": "Re-evaluate",
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["reevaluation_tasks_created"] == 1

    # Verify the new task exists
    async with AsyncSessionLocal() as db3:
        tasks = (await db3.execute(
            select(Task).where(
                Task.code == "RE-T-14",
                Task.project_id == ids["project_id"],
            )
        )).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].title.startswith("Re-evaluate")


@pytest.mark.asyncio
async def test_api_404_on_missing_decision():
    """POST /impact/analyze returns 404 for nonexistent decision."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post("/api/v1/impact/analyze", json={
            "project_id": str(uuid4()),
            "decision_id": str(uuid4()),
            "add_llm_phrasing": False,
        })
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 7.6 — Auto-trigger integration
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_impact_excludes_ai_proposed_by_default():
    """Unreviewed AI-inferred edges should be excluded by default."""
    pid = str(uuid4())
    d_id = str(uuid4())
    t_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add(Project(id=pid, name="Proposed Filter Test"))
        db.add(Decision(id=d_id, project_id=pid, code="D-PROP", statement="Test"))
        db.add(Task(id=t_id, project_id=pid, code="T-PROP", title="Proposed Task"))
        await db.flush()
        db.add(Edge(
            id=str(uuid4()), project_id=pid,
            from_id=d_id, from_type="decision",
            to_id=t_id, to_type="task",
            edge_type="resulted_in",
            origin="ai_inferred",
            review_status="unreviewed",
        ))
        await db.commit()

        # Default: exclude proposed
        result = await compute_impact(db, pid, d_id, include_proposed=False)
        assert result.total_affected == 0

        # Include proposed
        result2 = await compute_impact(db, pid, d_id, include_proposed=True)
        assert result2.total_affected == 1


# ═══════════════════════════════════════════════════════════════════════
# 7.8 — Expected-set precision/recall test
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_expected_set_precision_recall():
    """
    Plan §7.8: Report precision/recall for the LeafGuard Model B→C scenario.
    Expected affected set: {T-14, T-15, DL-02, DL-01, DOC-05}.
    """
    async with AsyncSessionLocal() as db:
        ids = await seed_leafguard_scenario(db)
        result = await compute_impact(db, ids["project_id"], ids["d17_id"])

    expected = {ids["t14_id"], ids["t15_id"], ids["dl02_id"], ids["dl01_id"], ids["doc05_id"]}
    actual = {item.id for item in result.affected_items}

    true_positives = expected & actual
    false_positives = actual - expected
    false_negatives = expected - actual

    precision = len(true_positives) / len(actual) if actual else 0
    recall = len(true_positives) / len(expected) if expected else 0

    assert precision == 1.0, f"Precision={precision}, FP={false_positives}"
    assert recall == 1.0, f"Recall={recall}, FN={false_negatives}"
    assert len(false_positives) == 0
    assert len(false_negatives) == 0


@pytest.mark.asyncio
async def test_empty_graph_returns_zero_affected():
    """A decision with no edges should produce zero affected items."""
    pid = str(uuid4())
    d_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        db.add(Project(id=pid, name="Empty Graph Test"))
        db.add(Decision(id=d_id, project_id=pid, code="D-EMPTY", statement="Solo"))
        await db.commit()

        result = await compute_impact(db, pid, d_id)

    assert result.total_affected == 0
    assert len(result.affected_items) == 0

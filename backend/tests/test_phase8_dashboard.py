"""
Phase 8 — Dashboard, Coverage, Weekly Report, 2-Team Security Tests (Days 22–25)
"""
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.entities import (
    Project, Decision, Task, Claim, Experiment, ExperimentResult,
    Document, Chunk, Contradiction, StaleFlag, Edge, Milestone, Deliverable
)
from app.intelligence.coverage import evaluate_claim_coverage, get_project_coverage
from app.intelligence.health import compute_project_health
from app.graph.blocked_tasks import derive_task_blockage, derive_all_project_tasks_blockage
from app.intelligence.reports import generate_weekly_report


@pytest.fixture
async def setup_project():
    """Seed a clean project environment."""
    pid = str(uuid4())
    async with AsyncSessionLocal() as db:
        project = Project(id=pid, name="Phase 8 Test Project")
        db.add(project)
        await db.commit()
    return pid


@pytest.mark.asyncio
async def test_six_health_dimensions_returned(setup_project):
    """
    Plan §8.1 / PRD §14.8:
    Verify that GET /api/v1/projects/{id}/health returns all six concrete dimensions:
    execution, evidence_coverage, documentation_health, decision_stability,
    dependency_health, knowledge_consistency with documented threshold rules and no composite score gate.
    """
    pid = setup_project
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/v1/projects/{pid}/health")
        assert resp.status_code == 200
        data = resp.json()

        assert "dimensions" in data
        dimensions = data["dimensions"]
        expected_dims = {
            "execution",
            "evidence_coverage",
            "documentation_health",
            "decision_stability",
            "dependency_health",
            "knowledge_consistency",
        }
        assert set(dimensions.keys()) == expected_dims

        for dim_name in expected_dims:
            dim = dimensions[dim_name]
            assert dim["traffic_light"] in ("green", "amber", "red")
            assert len(dim["threshold_rule"]) > 10
            assert "metrics" in dim
            assert "drilldown_items" in dim

        assert "summary_lights" in data
        assert "green" in data["summary_lights"]


@pytest.mark.asyncio
async def test_claim_coverage_sufficiency_checklist(setup_project):
    """
    Plan §8.2 / PRD §14.4:
    Verify checklist-based sufficiency profile. Badge says 'Evidence incomplete: ...', never 'false'.
    """
    pid = setup_project
    c_id = str(uuid4())
    exp_id = str(uuid4())
    res_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        claim = Claim(
            id=c_id,
            project_id=pid,
            statement="Model B achieves 84% accuracy",
            metric="accuracy",
            value=84.0,
            dataset="LeafSet-field",
            condition=None,  # No baseline comparison
        )
        db.add(claim)

        # Single run, no variance, no baseline ref
        exp = Experiment(id=exp_id, project_id=pid, code="EXP-06", model="Model B")
        res = ExperimentResult(
            id=res_id,
            project_id=pid,
            experiment_id=exp_id,
            metric="accuracy",
            value=84.0,
            num_runs=1,
            variance=None,
            baseline_ref=None,
        )
        db.add_all([exp, res])
        await db.flush()

        # Link result to claim
        edge = Edge(
            id=str(uuid4()),
            project_id=pid,
            from_id=res_id,
            from_type="experiment_result",
            to_id=c_id,
            to_type="claim",
            edge_type="supports",
        )
        db.add(edge)
        await db.commit()

        cov = await evaluate_claim_coverage(db, claim)

    assert cov.taxonomy_status == "partially_supported"
    assert "Evidence incomplete" in cov.badge_text
    assert "false" not in cov.badge_text.lower()
    assert "no baseline comparison" in cov.missing_fields
    assert "no run count" in cov.missing_fields
    assert "no variance reported" in cov.missing_fields

    dimensions = {item.dimension: item.status for item in cov.checklist}
    assert dimensions["comparison_baseline"] == "missing"
    assert dimensions["sample_size_runs"] == "missing"
    assert dimensions["variance_or_statistical_test"] == "missing"
    assert dimensions["metric_value"] == "satisfied"
    assert dimensions["dataset_named"] == "satisfied"


@pytest.mark.asyncio
async def test_claim_coverage_taxonomies(setup_project):
    """
    Plan §8.2: Verify taxonomy: well_supported, unsupported, potentially_contradicted, potentially_stale.
    """
    pid = setup_project
    c_well_id = str(uuid4())
    c_unsupported_id = str(uuid4())
    c_contra_id = str(uuid4())
    exp_id = str(uuid4())
    res_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        c_well = Claim(
            id=c_well_id, project_id=pid,
            statement="Model B latency is 4.8ms vs baseline 12.0ms",
            metric="latency", value=4.8, dataset="Android-TFLite", condition="vs baseline",
        )
        c_unsupported = Claim(
            id=c_unsupported_id, project_id=pid,
            statement="Unverified assumption about battery drain",
        )
        c_contra = Claim(
            id=c_contra_id, project_id=pid,
            statement="Model B robustness on field images",
            metric="accuracy", value=84.0, dataset="LeafSet-field",
        )
        exp = Experiment(id=exp_id, project_id=pid, code="EXP-06")
        res = ExperimentResult(
            id=res_id, project_id=pid, experiment_id=exp_id,
            metric="latency", value=4.8, baseline_ref="Model A (12.0ms)",
            num_runs=5, variance=0.12, split="test",
        )
        db.add_all([c_well, c_unsupported, c_contra, exp, res])
        await db.flush()

        # Link evidence to c_well
        db.add(Edge(
            id=str(uuid4()), project_id=pid,
            from_id=res_id, from_type="experiment_result",
            to_id=c_well_id, to_type="claim", edge_type="supports",
        ))

        # Add open contradiction to c_contra
        db.add(Contradiction(
            id=str(uuid4()), project_id=pid,
            a_type="claim", a_id=c_contra_id,
            b_type="experiment_result", b_id=res_id,
            status="open", explanation="Field trial showed 78.5% instead of 84%",
        ))
        await db.commit()

        cov_well = await evaluate_claim_coverage(db, c_well)
        cov_unsupported = await evaluate_claim_coverage(db, c_unsupported)
        cov_contra = await evaluate_claim_coverage(db, c_contra)

    assert cov_well.taxonomy_status == "well_supported"
    assert cov_well.badge_text == "Well-supported"

    assert cov_unsupported.taxonomy_status == "unsupported"
    assert "Unsupported" in cov_unsupported.badge_text

    assert cov_contra.taxonomy_status == "potentially_contradicted"
    assert "contradicted" in cov_contra.badge_text.lower()


@pytest.mark.asyncio
async def test_blocked_task_derivation(setup_project):
    """
    Plan §8.5: Verify rule-based deduction of blocked tasks:
    - Upstream incomplete task blocks downstream task
    - Completing upstream unblocks downstream task
    - Superseded foundation decision blocks task
    - Manual override takes precedence
    """
    pid = setup_project
    t1_id = str(uuid4())
    t2_id = str(uuid4())
    t3_id = str(uuid4())
    d_superseded_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        t1 = Task(id=t1_id, project_id=pid, code="T-1", title="Setup pipeline", status="in_progress")
        t2 = Task(id=t2_id, project_id=pid, code="T-2", title="Run pipeline", status="todo")
        t3 = Task(id=t3_id, project_id=pid, code="T-3", title="Deploy model", status="todo")
        d_superseded = Decision(id=d_superseded_id, project_id=pid, code="D-OLD", statement="Use Model A", status="superseded")

        t3.origin_decision_id = d_superseded_id

        db.add_all([t1, t2, t3, d_superseded])
        await db.flush()

        # T-2 depends_on T-1
        db.add(Edge(
            id=str(uuid4()), project_id=pid,
            from_id=t1_id, from_type="task",
            to_id=t2_id, to_type="task", edge_type="depends_on",
        ))
        await db.commit()

        # Test T-2 is blocked by T-1
        t2_blockage = await derive_task_blockage(db, t2)
        assert t2_blockage.is_blocked is True
        assert t2_blockage.blockage_source == "upstream_task"
        assert "T-1" in t2_blockage.blocked_reason

        # Test T-3 is blocked by superseded decision
        t3_blockage = await derive_task_blockage(db, t3)
        assert t3_blockage.is_blocked is True
        assert t3_blockage.blockage_source == "superseded_decision"
        assert "D-OLD" in t3_blockage.blocked_reason

        # Complete T-1 and verify T-2 is now unblocked
        t1.status = "done"
        await db.commit()
        t2_unblocked = await derive_task_blockage(db, t2)
        assert t2_unblocked.is_blocked is False

        # Apply manual override on T-2
        t2.is_blocked = True
        t2.blocked_reason = "Waiting on hardware procurement"
        await db.commit()
        t2_manual = await derive_task_blockage(db, t2)
        assert t2_manual.is_blocked is True
        assert t2_manual.blockage_source == "manual_override"
        assert "hardware" in t2_manual.blocked_reason


@pytest.mark.asyncio
async def test_experiment_summary_endpoint(setup_project):
    """
    Plan §8.4 / PRD §14.6: Verify structured experiment summary endpoint.
    """
    pid = setup_project
    exp_id = str(uuid4())
    d_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        dec = Decision(id=d_id, project_id=pid, code="D-17", statement="Adopt MobileNetV3")
        exp = Experiment(
            id=exp_id, project_id=pid, code="EXP-06",
            hypothesis="MobileNetV3 benchmark", model="MobileNetV3-Small", dataset="LeafSet-field",
            owner="Karan", parameters={"lr": 0.001, "batch_size": 32},
        )
        res1 = ExperimentResult(
            id=str(uuid4()), project_id=pid, experiment_id=exp_id,
            metric="accuracy", value=84.2, unit="%", split="test", baseline_ref="Model A (78.0%)",
        )
        res2 = ExperimentResult(
            id=str(uuid4()), project_id=pid, experiment_id=exp_id,
            metric="latency", value=4.8, unit="ms", split="test", baseline_ref="Model A (12.0ms)",
        )
        db.add_all([dec, exp, res1, res2])
        await db.flush()

        db.add(Edge(
            id=str(uuid4()), project_id=pid,
            from_id=exp_id, from_type="experiment",
            to_id=d_id, to_type="decision", edge_type="supports",
        ))
        await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get(f"/api/v1/experiments/{exp_id}/summary")
        assert resp.status_code == 200
        data = resp.json()

        assert data["code"] == "EXP-06"
        assert len(data["results_table"]) == 2
        # Check exact numbers copied directly
        acc_entry = next(r for r in data["results_table"] if r["metric"] == "accuracy")
        assert acc_entry["value"] == 84.2
        assert "comparison_to_baseline" in data
        assert "accuracy" in data["comparison_to_baseline"]
        assert len(data["linked_decisions"]) == 1
        assert data["linked_decisions"][0]["code"] == "D-17"
        assert "[AI summary]" in data["ai_summary"]


@pytest.mark.asyncio
async def test_weekly_report_generation(setup_project):
    """
    Plan §8.3 / PRD §14.7: Verify weekly intelligence report deterministic assembly.
    """
    pid = setup_project
    async with AsyncSessionLocal() as db:
        # Add some records in the project
        db.add(Decision(id=str(uuid4()), project_id=pid, code="D-1", statement="Decision 1", status="active"))
        db.add(Task(id=str(uuid4()), project_id=pid, code="T-1", title="Task 1", status="in_progress"))
        db.add(Milestone(id=str(uuid4()), project_id=pid, name="Sprint 1 Milestone"))
        await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            f"/api/v1/reports/projects/{pid}/generate",
            json={"use_llm": False},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["project_id"] == pid
        sections = data["sections"]
        assert "executive_paragraph" in sections
        assert "decisions_made_or_changed" in sections
        assert "tasks_progress_and_blocked" in sections
        assert "milestone_risks" in sections
        assert len(sections["decisions_made_or_changed"]) == 1
        assert len(sections["tasks_progress_and_blocked"]) == 1

        # Test GET /reports/{id}
        rep_id = data["id"]
        get_resp = await ac.get(f"/api/v1/reports/{rep_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == rep_id


@pytest.mark.asyncio
async def test_two_team_permission_demo_and_isolation(setup_project):
    """
    Plan §8.7: Verify guest role cannot access team:engineering restricted documents
    in search or RAG expansion.
    """
    pid = setup_project
    doc_eng_id = str(uuid4())
    doc_public_id = str(uuid4())

    async with AsyncSessionLocal() as db:
        # Confidential engineering document
        doc_eng = Document(
            id=doc_eng_id, project_id=pid,
            title="Confidential Internal Architecture",
            content_text="Confidential backend encryption keys and cluster credentials.",
            visibility="team",
            visibility_team_id="team_edge",
        )
        # Public team document
        doc_public = Document(
            id=doc_public_id, project_id=pid,
            title="Public Product Roadmap",
            content_text="Public release roadmap for Q4 LeafGuard mobile app.",
            visibility="project",
            visibility_team_id=None,
        )
        chunk_eng = Chunk(
            id=str(uuid4()),
            project_id=pid,
            document_id=doc_eng_id,
            char_start=0,
            char_end=len(doc_eng.content_text),
            text=doc_eng.content_text,
        )
        chunk_public = Chunk(
            id=str(uuid4()),
            project_id=pid,
            document_id=doc_public_id,
            char_start=0,
            char_end=len(doc_public.content_text),
            text=doc_public.content_text,
        )
        db.add_all([doc_eng, doc_public, chunk_eng, chunk_public])
        await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Search as Guest (without engineering team scope)
        headers_guest = {
            "X-User-Role": "guest",
        }
        resp = await ac.get(
            f"/api/v1/search?project_id={pid}&q=Confidential",
            headers=headers_guest,
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        found_titles = [r.get("document_title") for r in results]
        assert "Confidential Internal Architecture" not in found_titles

        # 2. Guest can see public documents
        resp_pub = await ac.get(
            f"/api/v1/search?project_id={pid}&q=Roadmap",
            headers=headers_guest,
        )
        assert resp_pub.status_code == 200
        pub_results = resp_pub.json()["results"]
        assert any(r["document_title"] == "Public Product Roadmap" for r in pub_results)

        # 3. Member / Owner with team_edge in their scope CAN see Confidential Internal Architecture
        resp_owner = await ac.get(
            f"/api/v1/search?project_id={pid}&q=Confidential",
        )
        assert resp_owner.status_code == 200
        owner_results = resp_owner.json()["results"]
        assert any(r["document_title"] == "Confidential Internal Architecture" for r in owner_results)

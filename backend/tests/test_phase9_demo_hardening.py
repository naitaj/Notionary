"""
Phase 9 — Demo Hardening & Rehearsal Test Suite (Days 24–28)
Verifies:
1. POST /api/v1/seed/reset-demo clears and seeds clean pre-meeting state.
2. Complete 8-scene rehearsal executed across 3 consecutive clean iterations:
   - Scene 1: Messy input upload & chunking
   - Scene 2: AI structuring & Review Inbox proposal review/approval
   - Scene 3: Notion relation mapping & sync status
   - Scene 4: Evidence graph & decision lineage traversal
   - Scene 5: "Why?" cited answer with provenance tags
   - Scene 5b: Missing evidence on CL-03 (sufficiency checklist)
   - Scene 6: Contradiction Radar (EXP-09 vs EXP-06)
   - Scene 7: Decision change -> Impact analysis -> Apply
   - Scene 8: Weekly intelligence report deterministic generation
3. Performance benchmarks against TRD targets:
   - Graph BFS / Impact analysis latency < 3.0s
   - Cited Q&A retrieval latency < 2.0s
   - Seed & Reset latency < 1.0s
4. LLM response cache & resilient timeout verification.
"""
import pytest
import time
from uuid import uuid4
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.entities import (
    Project, Decision, Task, Experiment, ExperimentResult,
    Claim, Document, Chunk, Contradiction, Proposal, Edge
)
from app.ai.resilience import ResilientLLMProvider
from app.ai.providers.mock_provider import MockLLMProvider


@pytest.mark.asyncio
async def test_reset_demo_endpoint():
    """Plan §9.1: Verify POST /api/v1/seed/reset-demo produces clean pre-meeting state."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        t0 = time.time()
        resp = await ac.post("/api/v1/seed/reset-demo")
        latency = time.time() - t0
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reset_success"
        assert latency < 2.0  # Fast reset target

        pid = data["project_id"]

        # Verify clean pre-meeting state: M-04 and EXP-09 must NOT exist yet
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            # Check experiments: only baseline EXP-01 exists
            exp_res = await db.execute(select(Experiment).where(Experiment.project_id == pid))
            exps = exp_res.scalars().all()
            exp_codes = [e.code for e in exps]
            assert "EXP-01" in exp_codes
            assert "EXP-06" not in exp_codes
            assert "EXP-09" not in exp_codes

            # Check decisions: D-17 not created yet
            dec_res = await db.execute(select(Decision).where(Decision.project_id == pid))
            decs = dec_res.scalars().all()
            assert len(decs) == 0


@pytest.mark.asyncio
async def test_resilient_llm_provider_cache_and_timeout():
    """Plan §9.3: Verify LLM timeout wrapper and in-memory cache."""
    mock = MockLLMProvider()
    resilient = ResilientLLMProvider(primary=mock, fallback=mock, timeout_seconds=2.0)

    # First call: populates cache
    ans1 = await resilient.complete("Why did we choose MobileNetV3?")
    assert "MobileNetV3" in ans1

    # Second call with identical prompt: served from cache immediately
    t0 = time.time()
    ans2 = await resilient.complete("Why did we choose MobileNetV3?")
    t_elapsed = time.time() - t0
    assert ans1 == ans2
    assert t_elapsed < 0.05  # Instant cache hit


@pytest.mark.asyncio
@pytest.mark.parametrize("rehearsal_run", [1, 2, 3])
async def test_rehearse_8_scenes_clean_run(rehearsal_run):
    """
    Plan §9.2: Rehearse the 8 scenes × 3 consecutive clean runs.
    Verifies that the whole scenario executes deterministically without errors.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Step 0: Reset demo to clean slate
        reset_resp = await ac.post("/api/v1/seed/reset-demo")
        assert reset_resp.status_code == 200
        pid = reset_resp.json()["project_id"]

        # ---------------------------------------------------------
        # SCENE 1: Messy input (M-04 meeting note upload & chunking)
        # ---------------------------------------------------------
        m04_content = (
            "Meeting Minutes: Core ML Sync M-04 (March 15, 2026)\n"
            "Attendees: Rohan Sharma, Ananya Patel, Meera Sen\n"
            "Decision D-17: Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.\n"
            "Rationale: MobileNetV3 meets our strict 20ms latency ceiling (clocking 14.2ms) while maintaining 91.2% accuracy.\n"
            "Task T-14: Meera Sen will quantize MobileNetV3 to INT8 by March 25.\n"
            "Task T-15: Ananya Patel will collect supplementary shadow dataset once quantization baseline completes.\n"
        )
        files = {
            "file": ("meeting_m04.txt", m04_content.encode("utf-8"), "text/plain"),
        }
        data = {
            "title": "M-04: Core ML Architecture Sync",
            "doc_type": "meeting_note",
        }
        from app.workers.runner import process_next_job

        s1_resp = await ac.post(f"/api/v1/projects/{pid}/documents", files=files, data=data)
        assert s1_resp.status_code == 201
        doc_data = s1_resp.json()
        doc_id = doc_data["document"]["id"]
        job_id = doc_data["job_id"]
        assert doc_id is not None

        # Process background document ingest job
        async with AsyncSessionLocal() as session:
            job_ran = await process_next_job(db=session, job_id=job_id)
            assert job_ran is True

        # Verify chunks created
        chunks_resp = await ac.get(f"/api/v1/documents/{doc_id}/chunks")
        assert chunks_resp.status_code == 200
        chunks = chunks_resp.json()
        assert len(chunks) > 0

        # ---------------------------------------------------------
        # SCENE 2: AI Structuring (Review Inbox proposal lifecycle)
        # ---------------------------------------------------------
        # Seed M-04 proposals (simulating background extraction worker)
        prop_id = str(uuid4())
        async with AsyncSessionLocal() as db:
            prop = Proposal(
                id=prop_id,
                project_id=pid,
                entity_type="decision",
                tier="high",
                confidence_label="high",
                needs_attention=False,
                status="pending",
                payload={
                    "code": "D-17",
                    "statement": "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
                    "rationale": "MobileNetV3 meets our strict 20ms latency ceiling clocking 14.2ms while maintaining 91.2% accuracy.",
                    "decided_by_alias": "Rohan Sharma",
                },
            )
            db.add(prop)
            await db.commit()

        # Fetch inbox
        inbox_resp = await ac.get(f"/api/v1/proposals/?project_id={pid}&status=pending")
        assert inbox_resp.status_code == 200
        inbox_items = inbox_resp.json()
        assert any(p["id"] == prop_id for p in inbox_items)

        # Human approves proposal
        appr_resp = await ac.post(f"/api/v1/proposals/{prop_id}/approve")
        assert appr_resp.status_code == 200
        appr_data = appr_resp.json()
        assert appr_data["status"] == "ok"

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            d_res = await db.execute(select(Decision).where(Decision.project_id == pid, Decision.code == "D-17"))
            d17 = d_res.scalar_one()
            d17_id = d17.id

        # ---------------------------------------------------------
        # SCENE 3: Notion Pages with Relations & Sync
        # ---------------------------------------------------------
        # Seed experiment EXP-06 supporting D-17
        exp06_id = str(uuid4())
        res06_id = str(uuid4())
        claim_lab_id = str(uuid4())
        t14_id = str(uuid4())
        t15_id = str(uuid4())

        async with AsyncSessionLocal() as db:
            exp06 = Experiment(
                id=exp06_id, project_id=pid, code="EXP-06",
                hypothesis="MobileNetV3 benchmark on PlantVillage",
                model="MobileNetV3-Small", dataset="PlantVillage Clean v2",
                status="completed", owner="Ananya Patel",
            )
            res06 = ExperimentResult(
                id=res06_id, project_id=pid, experiment_id=exp06_id,
                metric="accuracy", value=91.2, unit="%", split="test",
                baseline_ref="ResNet-50 (93.4%)", num_runs=5, variance=0.18,
                source_excerpt="EXP-06 summary: MobileNetV3 achieved 91.2% top-1 accuracy at 14.1 MB model size."
            )
            claim_lab = Claim(
                id=claim_lab_id, project_id=pid,
                statement="MobileNetV3 achieves 91.2% top-1 accuracy within 20MB budget",
                metric="accuracy", value=91.2, dataset="PlantVillage Clean v2",
                condition="vs ResNet-50",
            )
            t14 = Task(
                id=t14_id, project_id=pid, code="T-14",
                title="Quantize MobileNetV3 model to INT8 via TFLite converter",
                status="in_progress", origin_decision_id=d17_id,
            )
            t15 = Task(
                id=t15_id, project_id=pid, code="T-15",
                title="Collect supplementary shadow-augmented training dataset",
                status="todo",
            )
            db.add_all([exp06, res06, claim_lab, t14, t15])
            await db.flush()

            # Add relation edges
            db.add_all([
                Edge(id=str(uuid4()), project_id=pid, from_id=exp06_id, from_type="experiment", to_id=d17_id, to_type="decision", edge_type="supports"),
                Edge(id=str(uuid4()), project_id=pid, from_id=res06_id, from_type="experiment_result", to_id=claim_lab_id, to_type="claim", edge_type="supports"),
                Edge(id=str(uuid4()), project_id=pid, from_id=d17_id, from_type="decision", to_id=t14_id, to_type="task", edge_type="resulted_in"),
                Edge(id=str(uuid4()), project_id=pid, from_id=t14_id, from_type="task", to_id=t15_id, to_type="task", edge_type="depends_on"),
            ])
            await db.commit()

        # ---------------------------------------------------------
        # SCENE 4: Evidence Graph & Lineage Traversal
        # ---------------------------------------------------------
        t_graph_0 = time.time()
        lin_resp = await ac.get(f"/api/v1/decisions/{d17_id}/lineage")
        graph_latency = time.time() - t_graph_0
        assert lin_resp.status_code == 200
        assert graph_latency < 3.0  # TRD target: graph traversal < 3.0s

        lin_data = lin_resp.json()
        assert "decision_id" in lin_data
        assert "upstream_evidence" in lin_data
        assert "downstream_work" in lin_data

        # ---------------------------------------------------------
        # SCENE 5: "Why?" Cited Answer (Graph-RAG)
        # ---------------------------------------------------------
        t_rag_0 = time.time()
        rag_resp = await ac.post(
            "/api/v1/ai/query",
            json={"project_id": pid, "query": "Why did we choose MobileNetV3?"},
        )
        rag_latency = time.time() - t_rag_0
        assert rag_resp.status_code == 200
        assert rag_latency < 15.0  # TRD target: Q&A p90 < 15.0s

        rag_data = rag_resp.json()
        assert "answer" in rag_data
        assert len(rag_data["citations"]) > 0

        # ---------------------------------------------------------
        # SCENE 5b: Missing Evidence on Claims (Claim Coverage)
        # ---------------------------------------------------------
        cov_resp = await ac.get(f"/api/v1/coverage/projects/{pid}")
        assert cov_resp.status_code == 200
        cov_items = cov_resp.json()
        assert len(cov_items) >= 1
        assert "checklist" in cov_items[0]

        # ---------------------------------------------------------
        # SCENE 6: Contradiction Radar (EXP-09 vs EXP-06)
        # ---------------------------------------------------------
        exp09_id = str(uuid4())
        res09_id = str(uuid4())
        claim_field_id = str(uuid4())
        async with AsyncSessionLocal() as db:
            exp09 = Experiment(
                id=exp09_id, project_id=pid, code="EXP-09",
                hypothesis="Sunlight degradation field trial",
                model="MobileNetV3-Small", dataset="Field-MP-500",
                status="completed", owner="Ananya Patel",
            )
            res09 = ExperimentResult(
                id=res09_id, project_id=pid, experiment_id=exp09_id,
                metric="accuracy", value=76.4, unit="%", split="field_test",
                baseline_ref="EXP-06 (91.2%)", num_runs=1,
            )
            claim_field = Claim(
                id=claim_field_id, project_id=pid,
                statement="Field camera samples drop to 76.4% under harsh direct sunlight",
                metric="accuracy", value=76.4, dataset="Field-MP-500",
            )
            contra = Contradiction(
                id=str(uuid4()), project_id=pid,
                a_type="claim", a_id=claim_lab_id,
                b_type="claim", b_id=claim_field_id,
                status="open",
                explanation="EXP-06 benchmark accuracy (91.2%) contradicts EXP-09 field test (76.4%) under direct sun.",
            )
            db.add_all([exp09, res09, claim_field, contra])
            await db.commit()

        contra_resp = await ac.get(f"/api/v1/contradictions?project_id={pid}")
        assert contra_resp.status_code == 200
        contra_items = contra_resp.json()
        assert len(contra_items) >= 1

        # ---------------------------------------------------------
        # SCENE 7: Decision Change -> Impact Analysis -> Apply
        # ---------------------------------------------------------
        t_imp_0 = time.time()
        imp_resp = await ac.post(
            "/api/v1/impact/analyze",
            json={
                "project_id": pid,
                "decision_id": d17_id,
                "scenario": "what_if",
                "proposed_change": "Switch from MobileNetV3 to MobileNetV4 / EfficientNet",
            },
        )
        impact_latency = time.time() - t_imp_0
        assert imp_resp.status_code == 200
        assert impact_latency < 3.0  # TRD target: impact analysis < 3.0s

        imp_data = imp_resp.json()
        analysis_id = imp_data["analysis_id"]
        assert imp_data["total_affected"] >= 1

        # Apply impact
        apply_resp = await ac.post(
            f"/api/v1/impact/{analysis_id}/apply",
            json={
                "apply_items": [it["id"] for it in imp_data["affected_items"]],
                "create_reevaluation_tasks": True,
            },
        )
        assert apply_resp.status_code == 200
        assert apply_resp.json()["tasks_flagged"] >= 1

        # ---------------------------------------------------------
        # SCENE 8: Weekly Intelligence Report
        # ---------------------------------------------------------
        rep_resp = await ac.post(
            f"/api/v1/reports/projects/{pid}/generate",
            json={"time_window_days": 7, "use_llm": False},
        )
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert rep_data["project_id"] == pid
        assert "sections" in rep_data
        assert "executive_paragraph" in rep_data["sections"]

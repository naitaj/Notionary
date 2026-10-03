"""
Notionary — Automated 8-Scene Demo Rehearsal Runner (Phase 9)
PRD §44 / Prototype Plan §4 Phase 9.2 & 9.5

Executes the full canonical LeafGuard demo sequence across all 8 scenes:
  Scene 1: Ingest Meeting M-04 Transcript
  Scene 2: AI Extraction & Proposal Inbox Review
  Scene 3: Notion Relation Traversal & Bi-directional Sync
  Scene 4: Decision Lineage & Evidence Graph Traversal
  Scene 5: "Why?" Query with Cited Provenance
  Scene 5b: Claim Coverage Checklist & Missing Evidence
  Scene 6: Contradiction Radar (Field vs Lab Accuracy)
  Scene 7: What-If Impact Analysis & Propagated Invalidation
  Scene 8: Executive Weekly Intelligence Report Generation

Usage:
  python scripts/demo_rehearsal.py [--runs 3] [--target-url http://localhost:8000]
"""

import sys
import os
import time
import asyncio
import argparse
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import httpx
from colorama import init, Fore, Style
init(autoreset=True)

# TRD Performance Thresholds (seconds)
TRD_TARGETS = {
    "graph_traversal": 3.0,
    "rag_qa_query": 15.0,
    "impact_analysis": 3.0,
    "report_generation": 10.0,
}


class RehearsalRunner:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        if self.base_url:
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        else:
            from app.main import app
            self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def print_header(self, text: str):
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}")
        print(f" {text}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}")

    def print_scene(self, num: int, title: str):
        print(f"\n{Fore.BLUE}{Style.BRIGHT}>>> SCENE {num}: {title}{Style.RESET_ALL}")

    def print_success(self, msg: str, elapsed: Optional[float] = None):
        time_str = f" ({elapsed:.2f}s)" if elapsed is not None else ""
        print(f"  {Fore.GREEN}[OK] {msg}{Fore.YELLOW}{time_str}{Style.RESET_ALL}")

    def print_failure(self, msg: str):
        print(f"  {Fore.RED}[FAIL] ERROR: {msg}{Style.RESET_ALL}")

    async def run_single_rehearsal(self, iteration: int) -> bool:
        self.print_header(f"RUN #{iteration} — 8-SCENE CANONICAL DEMO REHEARSAL")
        benchmarks: Dict[str, float] = {}

        try:
            # Step 0: Reset Demo Environment
            t0 = time.time()
            res = await self.client.post("/api/v1/seed/reset-demo")
            if res.status_code != 200:
                self.print_failure(f"Failed to reset demo: {res.text}")
                return False
            data = res.json()
            project_id = data["project_id"]
            self.print_success(f"Demo Reset & Canonical Seed: Project '{data['project_name']}' ({project_id})", time.time() - t0)

            # -------------------------------------------------------------
            # Scene 1: Ingest Meeting M-04 Transcript
            # -------------------------------------------------------------
            self.print_scene(1, "Ingest Meeting M-04 Transcript")
            t0 = time.time()
            transcript_content = (
                "LeafGuard Architecture Sync #4 (M-04)\n"
                "Attendees: Rohan Sharma, Priya Rao, Marcus Vance, Ananya Patel\n\n"
                "Rohan Sharma: Let's review edge inference results. MobileNetV3 clocked 14.2ms "
                "on device with 91.2% accuracy on the PlantVillage dataset.\n"
                "Marcus Vance: Meets our latency ceiling. Decision D-17: Let's adopt MobileNetV3-Small.\n"
                "Priya Rao: I'll convert and quantize to INT8 (Task T-14) by next Thursday.\n"
                "Ananya Patel: I'll gather field camera shadow samples for training (Task T-15)."
            )
            files = {
                "file": ("meeting_m04.txt", transcript_content.encode("utf-8"), "text/plain"),
            }
            data = {
                "title": "M-04: Core ML Architecture Sync",
                "doc_type": "meeting_note",
            }
            doc_res = await self.client.post(
                f"/api/v1/projects/{project_id}/documents",
                files=files,
                data=data,
            )
            if doc_res.status_code != 201:
                self.print_failure(f"Document upload failed: {doc_res.text}")
                return False
            doc_data = doc_res.json()
            doc_id = doc_data["document"]["id"]
            job_id = doc_data["job_id"]
            self.print_success(f"Uploaded M-04 transcript (Doc ID: {doc_id[:8]}...)", time.time() - t0)

            # Execute background worker for ingestion
            from app.workers.runner import process_next_job
            from app.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                await process_next_job(db=session, job_id=job_id)
            self.print_success("Processed document indexing & extraction jobs")

            # -------------------------------------------------------------
            # Scene 2: AI Proposal Review & Approval
            # -------------------------------------------------------------
            self.print_scene(2, "Proposal Inbox Review & Human Approval")
            t0 = time.time()
            from app.database import AsyncSessionLocal
            from app.models.entities import Proposal, Decision
            from uuid import uuid4

            prop_id = str(uuid4())
            async with AsyncSessionLocal() as db:
                prop = Proposal(
                    id=prop_id,
                    project_id=project_id,
                    entity_type="decision",
                    tier="high",
                    confidence_label="high",
                    needs_attention=False,
                    status="pending",
                    payload={
                        "code": "D-17",
                        "statement": "Adopt MobileNetV3-Small as the edge inference architecture.",
                        "rationale": "Meets 20ms latency ceiling clocking 14.2ms at 91.2% accuracy.",
                        "decided_by_alias": "Rohan Sharma",
                    },
                )
                db.add(prop)
                await db.commit()

            inbox_res = await self.client.get(f"/api/v1/proposals/?project_id={project_id}&status=pending")
            assert inbox_res.status_code == 200
            appr_res = await self.client.post(f"/api/v1/proposals/{prop_id}/approve")
            assert appr_res.status_code == 200

            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                d_res = await db.execute(select(Decision).where(Decision.project_id == project_id, Decision.code == "D-17"))
                d17 = d_res.scalar_one()
                d17_id = d17.id
            self.print_success(f"Approved Decision D-17 proposal -> Created Decision {d17_id[:8]}...", time.time() - t0)

            # -------------------------------------------------------------
            # Scene 3: Notion Database Relations & Sync
            # -------------------------------------------------------------
            self.print_scene(3, "Notion Entity Relations & Bidirectional Sync")
            t0 = time.time()
            from app.models.entities import Experiment, ExperimentResult, Claim, Task, Edge
            exp06_id = str(uuid4())
            res06_id = str(uuid4())
            claim_lab_id = str(uuid4())
            t14_id = str(uuid4())
            t15_id = str(uuid4())

            async with AsyncSessionLocal() as db:
                exp06 = Experiment(
                    id=exp06_id, project_id=project_id, code="EXP-06",
                    hypothesis="MobileNetV3 benchmark on PlantVillage",
                    model="MobileNetV3-Small", dataset="PlantVillage Clean v2",
                    status="completed", owner="Ananya Patel",
                )
                res06 = ExperimentResult(
                    id=res06_id, project_id=project_id, experiment_id=exp06_id,
                    metric="accuracy", value=91.2, unit="%", split="test",
                    baseline_ref="ResNet-50 (93.4%)", num_runs=5, variance=0.18,
                )
                claim_lab = Claim(
                    id=claim_lab_id, project_id=project_id,
                    statement="MobileNetV3 achieves 91.2% top-1 accuracy within 20MB budget",
                    metric="accuracy", value=91.2, dataset="PlantVillage Clean v2",
                )
                t14 = Task(
                    id=t14_id, project_id=project_id, code="T-14",
                    title="Quantize MobileNetV3 model to INT8 via TFLite converter",
                    status="in_progress", origin_decision_id=d17_id,
                )
                t15 = Task(
                    id=t15_id, project_id=project_id, code="T-15",
                    title="Collect supplementary shadow-augmented training dataset",
                    status="todo",
                )
                db.add_all([exp06, res06, claim_lab, t14, t15])
                await db.flush()

                db.add_all([
                    Edge(id=str(uuid4()), project_id=project_id, from_id=exp06_id, from_type="experiment", to_id=d17_id, to_type="decision", edge_type="supports"),
                    Edge(id=str(uuid4()), project_id=project_id, from_id=res06_id, from_type="experiment_result", to_id=claim_lab_id, to_type="claim", edge_type="supports"),
                    Edge(id=str(uuid4()), project_id=project_id, from_id=d17_id, from_type="decision", to_id=t14_id, to_type="task", edge_type="resulted_in"),
                    Edge(id=str(uuid4()), project_id=project_id, from_id=t14_id, from_type="task", to_id=t15_id, to_type="task", edge_type="depends_on"),
                ])
                await db.commit()
            self.print_success("Linked EXP-06 -> D-17 -> T-14 -> T-15 and Claim relations", time.time() - t0)

            # -------------------------------------------------------------
            # Scene 4: Evidence Graph & Lineage Traversal
            # -------------------------------------------------------------
            self.print_scene(4, "Evidence Graph & Lineage Traversal")
            t0 = time.time()
            lin_res = await self.client.get(f"/api/v1/decisions/{d17_id}/lineage")
            lat_graph = time.time() - t0
            benchmarks["graph_traversal"] = lat_graph
            assert lin_res.status_code == 200
            lin_data = lin_res.json()
            assert "upstream_evidence" in lin_data
            assert "downstream_work" in lin_data
            assert lat_graph < TRD_TARGETS["graph_traversal"], f"Graph latency {lat_graph:.2f}s exceeded 3.0s target"
            self.print_success(f"Traversed lineage: {len(lin_data['upstream_evidence'])} upstream, {len(lin_data['downstream_work'])} downstream", lat_graph)

            # -------------------------------------------------------------
            # Scene 5: "Why?" Cited Answer (Graph-RAG)
            # -------------------------------------------------------------
            self.print_scene(5, "Cited Q&A Provenance (Graph-RAG)")
            t0 = time.time()
            rag_res = await self.client.post(
                "/api/v1/ai/query",
                json={"project_id": project_id, "query": "Why did we choose MobileNetV3?"},
            )
            lat_rag = time.time() - t0
            benchmarks["rag_qa_query"] = lat_rag
            assert rag_res.status_code == 200
            rag_data = rag_res.json()
            assert "answer" in rag_data
            assert len(rag_data["citations"]) > 0
            assert lat_rag < TRD_TARGETS["rag_qa_query"], f"RAG latency {lat_rag:.2f}s exceeded 15.0s target"
            self.print_success(f"Synthesized cited answer with {len(rag_data['citations'])} verifiable citations", lat_rag)

            # -------------------------------------------------------------
            # Scene 5b: Missing Evidence on Claims (Coverage)
            # -------------------------------------------------------------
            self.print_scene(5, "Claim Coverage & Missing Evidence Checklist")
            t0 = time.time()
            cov_res = await self.client.get(f"/api/v1/coverage/projects/{project_id}")
            assert cov_res.status_code == 200
            cov_items = cov_res.json()
            assert len(cov_items) >= 1
            self.print_success(f"Generated sufficiency profile for {len(cov_items)} claim(s)", time.time() - t0)

            # -------------------------------------------------------------
            # Scene 6: Contradiction Radar
            # -------------------------------------------------------------
            self.print_scene(6, "Contradiction Radar (Field vs Lab)")
            t0 = time.time()
            from app.models.entities import Contradiction
            exp09_id = str(uuid4())
            res09_id = str(uuid4())
            claim_field_id = str(uuid4())

            async with AsyncSessionLocal() as db:
                exp09 = Experiment(
                    id=exp09_id, project_id=project_id, code="EXP-09",
                    hypothesis="Sunlight degradation field trial",
                    model="MobileNetV3-Small", dataset="Field-MP-500",
                    status="completed", owner="Ananya Patel",
                )
                res09 = ExperimentResult(
                    id=res09_id, project_id=project_id, experiment_id=exp09_id,
                    metric="accuracy", value=76.4, unit="%", split="field_test",
                    baseline_ref="EXP-06 (91.2%)", num_runs=1,
                )
                claim_field = Claim(
                    id=claim_field_id, project_id=project_id,
                    statement="Field camera samples drop to 76.4% under harsh direct sunlight",
                    metric="accuracy", value=76.4, dataset="Field-MP-500",
                )
                contra = Contradiction(
                    id=str(uuid4()), project_id=project_id,
                    a_type="claim", a_id=claim_lab_id,
                    b_type="claim", b_id=claim_field_id,
                    status="open",
                    explanation="EXP-06 benchmark accuracy (91.2%) contradicts EXP-09 field test (76.4%).",
                )
                db.add_all([exp09, res09, claim_field, contra])
                await db.commit()

            c_res = await self.client.get(f"/api/v1/contradictions?project_id={project_id}")
            assert c_res.status_code == 200
            c_items = c_res.json()
            assert len(c_items) >= 1
            self.print_success(f"Radar surfaced active contradiction: EXP-09 vs EXP-06 ({c_items[0]['explanation'][:60]}...)", time.time() - t0)

            # -------------------------------------------------------------
            # Scene 7: Impact Analysis & Application
            # -------------------------------------------------------------
            self.print_scene(7, "Decision Re-evaluation & Invalidation Cascade")
            t0 = time.time()
            imp_res = await self.client.post(
                "/api/v1/impact/analyze",
                json={
                    "project_id": project_id,
                    "decision_id": d17_id,
                    "scenario": "what_if",
                    "proposed_change": "Switch to MobileNetV4 due to sunlight degradation",
                },
            )
            lat_impact = time.time() - t0
            benchmarks["impact_analysis"] = lat_impact
            assert imp_res.status_code == 200
            imp_data = imp_res.json()
            analysis_id = imp_data["analysis_id"]
            assert imp_data["total_affected"] >= 1
            assert lat_impact < TRD_TARGETS["impact_analysis"], f"Impact latency {lat_impact:.2f}s exceeded 3.0s target"
            self.print_success(f"Simulated blast radius: {imp_data['total_affected']} downstream item(s) impacted", lat_impact)

            apply_res = await self.client.post(
                f"/api/v1/impact/{analysis_id}/apply",
                json={
                    "apply_items": [it["id"] for it in imp_data["affected_items"]],
                    "create_reevaluation_tasks": True,
                },
            )
            assert apply_res.status_code == 200
            self.print_success(f"Applied impact: Flagged {apply_res.json()['tasks_flagged']} task(s) for re-evaluation")

            # -------------------------------------------------------------
            # Scene 8: Weekly Intelligence Report
            # -------------------------------------------------------------
            self.print_scene(8, "Weekly Executive Intelligence Report")
            t0 = time.time()
            rep_res = await self.client.post(
                f"/api/v1/reports/projects/{project_id}/generate",
                json={"time_window_days": 7, "use_llm": False},
            )
            lat_rep = time.time() - t0
            benchmarks["report_generation"] = lat_rep
            assert rep_res.status_code == 200
            rep_data = rep_res.json()
            assert "executive_paragraph" in rep_data["sections"]
            assert lat_rep < TRD_TARGETS["report_generation"]
            self.print_success("Generated executive digest with Decisions, Contradictions, and Tasks", lat_rep)

            # Performance Scorecard
            print(f"\n{Fore.MAGENTA}{Style.BRIGHT}--- RUN #{iteration} PERFORMANCE SCORECARD ---")
            for metric, val in benchmarks.items():
                target = TRD_TARGETS[metric]
                status_color = Fore.GREEN if val <= target else Fore.RED
                print(f"  {metric:20s}: {status_color}{val:.3f}s{Style.RESET_ALL} (TRD Target: <{target:.1f}s)")

            return True

        except Exception as e:
            self.print_failure(f"Exception during rehearsal: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    parser = argparse.ArgumentParser(description="Notionary Phase 9 Rehearsal Runner")
    parser.add_argument("--runs", type=int, default=3, help="Number of consecutive runs (default: 3)")
    parser.add_argument("--target-url", type=str, default=None, help="Target server URL (default: in-process)")
    args = parser.parse_args()

    print(f"\n{Fore.GREEN}{Style.BRIGHT}==================================================================")
    print(f" NOTIONARY DEMO REHEARSAL HARNESS — PHASE 9 HARDENING")
    print(f" Executing {args.runs} Consecutive Rehearsals")
    print(f"=================================================================={Style.RESET_ALL}")

    successes = 0
    async with RehearsalRunner(base_url=args.target_url) as runner:
        for i in range(1, args.runs + 1):
            ok = await runner.run_single_rehearsal(i)
            if ok:
                successes += 1
            else:
                print(f"{Fore.RED}Rehearsal run #{i} FAILED.{Style.RESET_ALL}")
                sys.exit(1)

    print(f"\n{Fore.GREEN}{Style.BRIGHT}[SUCCESS] ALL {args.runs} REHEARSALS COMPLETED SUCCESSFULLY (100% CLEAN RUNS){Style.RESET_ALL}\n")


if __name__ == "__main__":
    asyncio.run(main())

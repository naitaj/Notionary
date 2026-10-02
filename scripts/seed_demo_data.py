import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Ensure backend root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import (
    User, Project, Team, ProjectMember, Person,
    Document, Chunk, Excerpt, Meeting, Reference, Claim,
    Experiment, ExperimentResult, Decision, Task, Milestone, Deliverable,
    Edge, Contradiction, StaleFlag, DatasetAlias, AuditLog
)

async def seed_leafguard():
    print("Seeding LeafGuard Reference Prototype Data (PRD §29 / Plan Phase 0)...")

    # 1. Initialize schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if project already exists
        res = await session.execute(select(Project).where(Project.name == "LeafGuard: Edge Crop Disease Detector"))
        existing_project = res.scalars().first()
        if existing_project:
            print(f"LeafGuard project already exists (ID: {existing_project.id}). Resetting data...")
            # Delete project-scoped records to ensure clean reproducible demo state
            pid = existing_project.id
            for model in [Edge, Contradiction, StaleFlag, Task, Deliverable, Milestone, Decision,
                          ExperimentResult, Experiment, Claim, Reference, Meeting, Document,
                          Person, Team, ProjectMember]:
                await session.execute(delete(model).where(model.project_id == pid))
            await session.commit()
            project = existing_project
        else:
            project = Project(
                name="LeafGuard: Edge Crop Disease Detector",
                description="On-device deep learning system for offline crop disease diagnosis in rural farms (KBC 2026 Reference Scenario).",
                notion_parent_id="notion-page-leafguard-root",
            )
            session.add(project)
            await session.flush()

        project_id = project.id

        # 2. Users & Teams
        karan_user = User(id="usr_karan", email="karan@leafguard.ai", display_name="Karan Mehta")
        ananya_user = User(id="usr_ananya", email="ananya@leafguard.ai", display_name="Ananya Patel")
        guest_user = User(id="usr_guest", email="auditor@external.org", display_name="Independent Auditor")
        session.add_all([karan_user, ananya_user, guest_user])

        team_ml = Team(id="team_ml", project_id=project_id, name="ML & Modeling")
        team_edge = Team(id="team_edge", project_id=project_id, name="Edge Deployment")
        session.add_all([team_ml, team_edge])
        await session.flush()

        session.add_all([
            ProjectMember(project_id=project_id, user_id=karan_user.id, role="owner", team_id=team_ml.id),
            ProjectMember(project_id=project_id, user_id=ananya_user.id, role="member", team_id=team_ml.id),
            ProjectMember(project_id=project_id, user_id=guest_user.id, role="guest", team_id=None),
        ])

        # 3. People
        karan = Person(id="person_karan", project_id=project_id, display_name="Karan Mehta", aliases=["Karan", "Lead", "karan@leafguard.ai"], user_id=karan_user.id)
        ananya = Person(id="person_ananya", project_id=project_id, display_name="Ananya Patel", aliases=["Ananya", "Researcher", "ananya@leafguard.ai"], user_id=ananya_user.id)
        vikram = Person(id="person_vikram", project_id=project_id, display_name="Vikram Singh", aliases=["Vikram", "Edge Eng", "vikram@leafguard.ai"])
        priya = Person(id="person_priya", project_id=project_id, display_name="Priya Sharma", aliases=["Priya", "Agronomist"])
        session.add_all([karan, ananya, vikram, priya])
        await session.flush()

        # 4. References & Documents
        r01 = Reference(
            project_id=project_id,
            title="MobileNetV3: Searching for MobileNetV3 (Howard et al., 2019)",
            authors="Andrew Howard, Mark Sandler et al.",
            year=2019,
            url_or_doi="https://arxiv.org/abs/1905.02244",
            key_takeaways="Hardware-aware NAS combined with NetAdapt achieves state-of-the-art accuracy with sub-20ms latency on ARM cores.",
            notion_page_id="notion-ref-r01",
        )
        r02 = Reference(
            project_id=project_id,
            title="Field Deployment Constraints for Edge Agricultural Scanners (ICAR Technical Report 2025)",
            authors="Indian Council of Agricultural Research",
            year=2025,
            url_or_doi="https://icar.gov.in/edge-diagnostics-2025",
            key_takeaways="Handheld farmer scanners require maximum 20ms latency and resilient battery life under ambient temperatures exceeding 40°C.",
            notion_page_id="notion-ref-r02",
        )
        doc05 = Document(
            id="doc_05",
            project_id=project_id,
            title="DOC-05: LeafGuard Server Architecture & Edge Inference Pipeline",
            doc_type="design_doc",
            file_uri="fixtures/leafguard/DOC-05.md",
            content_text="Server and edge architecture specification for LeafGuard. On-device inference relies on MobileNetV3-Small exported engine.",
            doc_date=datetime(2026, 2, 20, tzinfo=timezone.utc),
            pipeline_status="completed",
            notion_page_id="notion-doc-05",
        )
        session.add_all([r01, r02, doc05])
        await session.flush()

        # 5. Experiments & Results
        exp06 = Experiment(
            id="exp_06",
            project_id=project_id,
            code="EXP-06",
            hypothesis="MobileNetV3 backbone provides sufficient accuracy within the 20ms edge latency envelope on Jetson Nano.",
            model="MobileNetV3-Small",
            dataset="PlantVillage Clean v2 (14 classes)",
            parameters={"batch_size": 1, "precision": "FP16", "framework": "TensorRT"},
            status="completed",
            owner_id=karan.id,
            run_date=datetime(2026, 3, 10, tzinfo=timezone.utc),
            notion_page_id="notion-exp-06",
        )
        exp09 = Experiment(
            id="exp_09",
            project_id=project_id,
            code="EXP-09",
            hypothesis="Model robustness under direct midday harsh sunlight and shadow variations on Madhya Pradesh soybean fields.",
            model="MobileNetV3-Small",
            dataset="Field Collected Rural MP (500 photos)",
            parameters={"lighting": "direct_harsh_sun", "ambient_temp_c": 41},
            status="completed",
            owner_id=ananya.id,
            run_date=datetime(2026, 3, 22, tzinfo=timezone.utc),
            notion_page_id="notion-exp-09",
        )
        session.add_all([exp06, exp09])
        await session.flush()

        res06 = ExperimentResult(
            project_id=project_id,
            experiment_id=exp06.id,
            metric="f1_score",
            value=88.2,
            unit="%",
            split="val",
            num_runs=3,
            variance=0.5,
            source_excerpt="Benchmarked MobileNetV3-Small on Jetson Nano: 14.2ms latency, 88.2% F1 score.",
        )
        res09 = ExperimentResult(
            project_id=project_id,
            experiment_id=exp09.id,
            metric="f1_score",
            value=78.5,
            unit="%",
            split="field",
            num_runs=5,
            variance=2.4,
            source_excerpt="EXP-09 test on 500 ground-truth infected leaves under harsh noon sunlight dropped F1 to 78.5%.",
        )
        session.add_all([res06, res09])
        await session.flush()

        # 6. Claims
        cl02 = Claim(
            id="cl_02",
            project_id=project_id,
            statement="MobileNetV3-Small is robust across lighting conditions with 88.2% F1 score.",
            claim_type="observation",
            subject="MobileNetV3-Small",
            metric="f1_score",
            direction="increase",
            dataset="PlantVillage Clean v2",
            value=88.2,
            coverage_status="supported",
            source_excerpt="Validation tests demonstrate 88.2% F1 score across 14 crop disease categories.",
            document_id=doc05.id,
            notion_page_id="notion-claim-02",
        )
        cl04 = Claim(
            id="cl_04",
            project_id=project_id,
            statement="Model B delivers superior inference efficiency over Model A on ARM platforms with <15ms latency.",
            claim_type="comparative",
            subject="MobileNetV3-Small",
            metric="latency_ms",
            direction="decrease",
            dataset="PlantVillage Clean v2",
            value=14.2,
            coverage_status="supported",
            source_excerpt="Model B executes in 14.2ms vs 31.8ms for Model A.",
            document_id=doc05.id,
            notion_page_id="notion-claim-04",
        )
        session.add_all([cl02, cl04])
        await session.flush()

        # 7. Decisions (Back-dated to historical timeline per PRD §29.5)
        d17 = Decision(
            id="dec_d17",
            project_id=project_id,
            code="D-17",
            statement="Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            rationale="MobileNetV3-Small achieves 88.2% F1 score at 14.2ms latency, fulfilling the 20ms constraint defined in R-02 and outperforming ResNet-18 (Model A) on battery and thermal efficiency.",
            alternatives=[
                {"name": "Model A (ResNet-18)", "metric": "31.8ms latency", "reason": "Violated 20ms hardware ceiling and excessive power draw"},
                {"name": "EfficientNet-Lite0", "metric": "22.4ms latency", "reason": "Higher memory footprint without significant accuracy gain"}
            ],
            status="active",
            version=1,
            decided_on=datetime(2026, 3, 15, tzinfo=timezone.utc),
            decided_by="Karan Mehta",
            decided_by_id=karan.id,
            effective_from=datetime(2026, 3, 15, tzinfo=timezone.utc),
            origin="human_authored",
            review_status="approved",
            notion_page_id="notion-dec-d17",
            notion_url="https://notion.so/workspace/d17-mobilenetv3-selection",
        )
        session.add(d17)
        await session.flush()

        # 8. Tasks & Milestones
        milestone = Milestone(
            id="ms_01",
            project_id=project_id,
            name="Milestone 1: Q1 On-Device Model Validation",
            due_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
            progress_percentage=65,
            notion_page_id="notion-ms-01",
        )
        session.add(milestone)
        await session.flush()

        t14 = Task(
            id="task_t14",
            project_id=project_id,
            code="T-14",
            title="Quantize MobileNetV3-Small to INT8 via TensorRT-LLM and benchmark precision",
            status="in_progress",
            owner="Ananya Patel",
            owner_id=ananya.id,
            due_date=datetime(2026, 3, 25, tzinfo=timezone.utc),
            priority="high",
            origin_decision_id=d17.id,
            is_blocked=False,
            needs_reevaluation=False,
            notion_page_id="notion-task-t14",
        )
        t15 = Task(
            id="task_t15",
            project_id=project_id,
            code="T-15",
            title="Integrate MobileNetV3-Small inference pipeline into Android camera capture daemon",
            status="todo",
            owner="Vikram Singh",
            owner_id=vikram.id,
            due_date=datetime(2026, 3, 28, tzinfo=timezone.utc),
            priority="medium",
            origin_decision_id=d17.id,
            is_blocked=False,
            needs_reevaluation=False,
            notion_page_id="notion-task-t15",
        )
        dl01 = Deliverable(
            id="dl_01",
            project_id=project_id,
            name="Quantized MobileNetV3 TensorRT Weights",
            deliverable_type="weights",
            status="in_progress",
            due_date=datetime(2026, 3, 26, tzinfo=timezone.utc),
            milestone_id=milestone.id,
            notion_page_id="notion-dl-01",
        )
        dl02 = Deliverable(
            id="dl_02",
            project_id=project_id,
            name="Field Diagnostics Android APK Build",
            deliverable_type="apk",
            status="todo",
            due_date=datetime(2026, 3, 29, tzinfo=timezone.utc),
            milestone_id=milestone.id,
            notion_page_id="notion-dl-02",
        )
        session.add_all([t14, t15, dl01, dl02])
        await session.flush()

        # 9. Typed Graph Edges (PRD §29.7 & Plan §1.2 Issue 4/5)
        edges = [
            Edge(project_id=project_id, from_type="reference", from_id=r02.id, to_type="claim", to_id=cl04.id, edge_type="supports", rationale_text="ICAR technical report mandates sub-20ms edge latency ceiling."),
            Edge(project_id=project_id, from_type="experiment", from_id=exp06.id, to_type="claim", to_id=cl02.id, edge_type="supports", rationale_text="EXP-06 benchmark data confirms 88.2% F1 accuracy on validation split."),
            Edge(project_id=project_id, from_type="claim", from_id=cl02.id, to_type="decision", to_id=d17.id, edge_type="supports", rationale_text="Accuracy & efficiency claims form primary evidence for selecting Model B."),
            Edge(project_id=project_id, from_type="decision", from_id=d17.id, to_type="task", to_id=t14.id, edge_type="resulted_in", rationale_text="D-17 directly commissioned quantization task T-14."),
            Edge(project_id=project_id, from_type="decision", from_id=d17.id, to_type="task", to_id=t15.id, edge_type="resulted_in", rationale_text="D-17 directly commissioned edge daemon integration task T-15."),
            Edge(project_id=project_id, from_type="task", from_id=t14.id, to_type="deliverable", to_id=dl01.id, edge_type="contributes_to", rationale_text="Completion of T-14 produces quantized model binary DL-01."),
            Edge(project_id=project_id, from_type="task", from_id=t15.id, to_type="deliverable", to_id=dl02.id, edge_type="contributes_to", rationale_text="Completion of T-15 produces field APK build DL-02."),
            Edge(project_id=project_id, from_type="decision", from_id=d17.id, to_type="document", to_id=doc05.id, edge_type="describes", rationale_text="DOC-05 explicitly describes the edge inference pipeline adopted in D-17."),
        ]
        session.add_all(edges)

        # 10. Seeded Contradiction (Polymorphic: ExperimentResult vs Claim)
        contradiction = Contradiction(
            project_id=project_id,
            a_type="claim",
            a_id=cl02.id,
            b_type="experiment_result",
            b_id=res09.id,
            detection_method="both",
            status="open",
            explanation="EXP-09 observed 78.5% F1 score in direct midday sunlight, contradicting claim CL-02 asserting 88.2% robustness across lighting conditions (delta = -9.7%).",
        )
        session.add(contradiction)

        # 11. Dataset Aliases
        aliases = [
            DatasetAlias(project_id=project_id, kind="subject", canonical="MobileNetV3-Small", alias="Model B"),
            DatasetAlias(project_id=project_id, kind="subject", canonical="ResNet-18", alias="Model A"),
            DatasetAlias(project_id=project_id, kind="dataset", canonical="LeafSet-field", alias="Field Collected Rural MP"),
            DatasetAlias(project_id=project_id, kind="metric", canonical="f1_score", alias="accuracy"),
        ]
        session.add_all(aliases)

        # 12. Audit Log Entry
        audit = AuditLog(
            project_id=project_id,
            actor_id="system",
            actor_type="system",
            action="seed_demo_baseline",
            entity_type="project",
            entity_id=project_id,
            after_state={"name": project.name, "seed_version": "v1.0-phase0"},
        )
        session.add(audit)

        await session.commit()
        print(f"SUCCESS: Seeded LeafGuard Demo Dataset with Project ID: {project_id}")

if __name__ == "__main__":
    asyncio.run(seed_leafguard())

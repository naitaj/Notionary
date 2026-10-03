from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models.entities import (
    Project, Person, Decision, Task, Experiment, ExperimentResult,
    Claim, Deliverable, Milestone, Contradiction, Edge, Document,
    Chunk, Proposal, Reference, StaleFlag, Meeting
)

router = APIRouter(prefix="/seed", tags=["Seed Data"])

PROJECT_NAME = "LeafGuard: Edge Crop Disease Detector"

async def _clean_project_data(db: AsyncSession, project_id: str):
    """Truncates/removes all entities associated with the given project."""
    await db.execute(delete(Edge).where(Edge.project_id == project_id))
    await db.execute(delete(Contradiction).where(Contradiction.project_id == project_id))
    await db.execute(delete(StaleFlag).where(StaleFlag.project_id == project_id))
    await db.execute(delete(Proposal).where(Proposal.project_id == project_id))
    await db.execute(delete(Chunk).where(Chunk.project_id == project_id))
    await db.execute(delete(Document).where(Document.project_id == project_id))
    await db.execute(delete(Meeting).where(Meeting.project_id == project_id))
    await db.execute(delete(ExperimentResult).where(ExperimentResult.project_id == project_id))
    await db.execute(delete(Experiment).where(Experiment.project_id == project_id))
    await db.execute(delete(Claim).where(Claim.project_id == project_id))
    await db.execute(delete(Task).where(Task.project_id == project_id))
    await db.execute(delete(Decision).where(Decision.project_id == project_id))
    await db.execute(delete(Deliverable).where(Deliverable.project_id == project_id))
    await db.execute(delete(Milestone).where(Milestone.project_id == project_id))
    await db.execute(delete(Reference).where(Reference.project_id == project_id))
    await db.execute(delete(Person).where(Person.project_id == project_id))
    await db.flush()


@router.post("/reset-demo")
async def reset_demo_state(db: AsyncSession = Depends(get_db)):
    """
    Task 9.1 / Plan §9.1:
    Truncates and seeds clean LeafGuard pre-demo state:
    - Persons, baseline references, milestones, and initial specs are seeded.
    - M-04 and EXP-09 are DELIBERATELY EXCLUDED so presenter can run live upload & structuring.
    """
    res = await db.execute(select(Project).where(Project.name == PROJECT_NAME))
    projects = res.scalars().all()

    if projects:
        project = projects[0]
        for dup in projects[1:]:
            await _clean_project_data(db, dup.id)
            await db.delete(dup)
        await _clean_project_data(db, project.id)
    else:
        project = Project(
            name=PROJECT_NAME,
            description="On-device deep learning system for offline crop disease diagnosis in rural farms (KBC 2026 Reference Scenario).",
            notion_parent_id="notion-page-leafguard-root",
        )
        db.add(project)
        await db.flush()

    pid = project.id

    # 1. Team Persons
    rohan = Person(project_id=pid, name="Rohan Sharma", email="rohan@leafguard.ai", aliases=["Lead", "Rohan"])
    ananya = Person(project_id=pid, name="Ananya Patel", email="ananya@leafguard.ai", aliases=["Researcher", "Ananya"])
    meera = Person(project_id=pid, name="Meera Sen", email="meera@leafguard.ai", aliases=["ML Eng", "Meera"])
    db.add_all([rohan, ananya, meera])

    # 2. Milestones & Deliverables
    m1 = Milestone(project_id=pid, name="Milestone 1: Feasibility Study", progress_percentage=100)
    m2 = Milestone(project_id=pid, name="Milestone 2: Field-Ready Prototype", progress_percentage=40)
    db.add_all([m1, m2])
    await db.flush()

    deliv_spec = Deliverable(
        project_id=pid,
        name="DL-01: System Architecture & Constraint Spec",
        deliverable_type="document",
        status="completed",
        milestone_id=m1.id,
    )
    deliv_apk = Deliverable(
        project_id=pid,
        name="DL-02: LeafGuard Android Prototype APK",
        deliverable_type="binary",
        status="in_progress",
        milestone_id=m2.id,
    )
    db.add_all([deliv_spec, deliv_apk])

    # 3. Baseline Reference Literature
    ref1 = Reference(
        project_id=pid,
        title="Howard et al., MobileNets: Efficient Convolutional Neural Networks for Mobile Vision",
        authors="Howard, A.G. et al.",
        year=2017,
        url_or_doi="arXiv:1704.04861",
        key_takeaways="Depthwise separable convolutions reduce parameter footprint by ~8x while retaining comparable accuracy.",
    )
    ref2 = Reference(
        project_id=pid,
        title="Mohanty et al., Using Deep Learning for Image-Based Plant Disease Detection",
        authors="Mohanty, S.P., Hughes, D.P., Salathé, M.",
        year=2016,
        url_or_doi="doi:10.3389/fpls.2016.01419",
        key_takeaways="PlantVillage benchmark achieves >99% under lab conditions, but cautions on field generalization drop.",
    )
    db.add_all([ref1, ref2])

    # 5. Baseline Exploratory Experiment
    exp01 = Experiment(
        project_id=pid,
        code="EXP-01",
        hypothesis="ResNet-50 baseline on PlantVillage dataset",
        model="ResNet-50",
        dataset="PlantVillage Clean v2",
        status="completed",
        owner="Meera Sen",
    )
    db.add(exp01)
    await db.flush()

    res01_acc = ExperimentResult(
        project_id=pid,
        experiment_id=exp01.id,
        metric="accuracy",
        value=93.4,
        unit="%",
        split="test",
        source_excerpt="EXP-01: ResNet-50 achieves 93.4% accuracy, but model size is 98.2 MB (exceeds 20MB budget).",
    )
    res01_size = ExperimentResult(
        project_id=pid,
        experiment_id=exp01.id,
        metric="model_size",
        value=98.2,
        unit="MB",
        split="test",
        source_excerpt="EXP-01: Model size 98.2 MB violates strict 20MB constraint.",
    )
    db.add_all([res01_acc, res01_size])

    await db.commit()
    return {
        "status": "reset_success",
        "project_id": pid,
        "project_name": PROJECT_NAME,
        "message": "Demo reset to clean pre-meeting state. Ready for M-04 upload and live extraction flow.",
    }


@router.post("/full-demo")
@router.post("/demo")
async def seed_full_demo(db: AsyncSession = Depends(get_db)):
    """
    Seeds the complete end-to-end LeafGuard state including:
    - M-04 approved decisions (D-17), tasks (T-14, T-15), claims, experiments (EXP-06, EXP-09),
    - Verified contradictions (sunlight degradation) and typed graph edges.
    """
    res = await db.execute(select(Project).where(Project.name == PROJECT_NAME))
    project = res.scalar_one_or_none()

    if project:
        await _clean_project_data(db, project.id)
    else:
        project = Project(
            name=PROJECT_NAME,
            description="On-device deep learning system for offline crop disease diagnosis in rural farms (KBC 2026 Reference Scenario).",
            notion_parent_id="notion-page-leafguard-root",
        )
        db.add(project)
        await db.flush()

    pid = project.id

    # 1. Team Persons
    rohan = Person(project_id=pid, name="Rohan Sharma", email="rohan@leafguard.ai", aliases=["Lead", "Rohan"])
    ananya = Person(project_id=pid, name="Ananya Patel", email="ananya@leafguard.ai", aliases=["Researcher", "Ananya"])
    meera = Person(project_id=pid, name="Meera Sen", email="meera@leafguard.ai", aliases=["ML Eng", "Meera"])
    db.add_all([rohan, ananya, meera])
    await db.flush()

    # 2. Experiments & Results
    exp06 = Experiment(
        project_id=pid,
        code="EXP-06",
        hypothesis="MobileNetV3 backbone provides sufficient accuracy within the 20MB edge memory envelope.",
        model="MobileNetV3-Small",
        dataset="PlantVillage Clean v2 (14 classes)",
        parameters={"epochs": 50, "batch_size": 32, "lr": 0.001, "quantization": "FP32"},
        status="completed",
        owner="Ananya Patel",
    )
    exp09 = Experiment(
        project_id=pid,
        code="EXP-09",
        hypothesis="Model robustness under direct afternoon sunlight and shadow variations.",
        model="MobileNetV3-Small",
        dataset="Field Collected Rural MP (500 photos)",
        parameters={"lighting": "direct_harsh_sun"},
        status="completed",
        owner="Ananya Patel",
    )
    db.add_all([exp06, exp09])
    await db.flush()

    res06 = ExperimentResult(
        project_id=pid,
        experiment_id=exp06.id,
        metric="Top-1 Accuracy",
        value=91.2,
        unit="%",
        split="test",
        baseline_ref="ResNet-50 (93.4%)",
        num_runs=5,
        variance=0.18,
        source_excerpt="EXP-06 summary: MobileNetV3 + data aug achieved 91.2% top-1 accuracy at 14.1 MB model size."
    )
    res09 = ExperimentResult(
        project_id=pid,
        experiment_id=exp09.id,
        metric="Top-1 Accuracy",
        value=76.4,
        unit="%",
        split="field_test",
        baseline_ref="EXP-06 Lab (91.2%)",
        num_runs=1,
        source_excerpt="EXP-09 field test: Severe degradation under harsh lighting to 76.4% top-1 accuracy."
    )
    db.add_all([res06, res09])
    await db.flush()

    # 3. Claims
    claim_lab = Claim(
        project_id=pid,
        statement="MobileNetV3 provides 91.2% top-1 accuracy and satisfies the <20MB edge memory budget.",
        claim_type="comparative",
        subject="MobileNetV3",
        metric="Top-1 Accuracy",
        value=91.2,
        direction="better",
        dataset="PlantVillage",
        condition="vs ResNet-50",
        status="supported",
        source_excerpt="EXP-06 result R-21: MobileNetV3 achieves 91.2% accuracy at 14 MB vs ResNet50 at 98 MB."
    )
    claim_field = Claim(
        project_id=pid,
        statement="Field camera samples suffer severe 14.8% accuracy drop due to harsh outdoor lighting variations.",
        claim_type="observation",
        subject="MobileNetV3 Field Reliability",
        metric="Accuracy Drop",
        value=14.8,
        direction="decrease",
        dataset="Field-MP-500",
        status="unverified",
        source_excerpt="EXP-09: Field images show significant false positives on cassava mosaic disease in bright glare."
    )
    claim_battery = Claim(
        project_id=pid,
        statement="Battery consumption will decrease by 30% with INT8 quantization on Android daemon.",
        claim_type="assumption",
        subject="Battery Efficiency",
        metric="Battery Saving",
        value=30.0,
        status="unsupported",
    )
    db.add_all([claim_lab, claim_field, claim_battery])
    await db.flush()

    # 4. Decisions
    d17 = Decision(
        project_id=pid,
        code="D-17",
        statement="Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
        rationale="Selected over ResNet50 (93.0% but 98MB) to stay strictly within the 20MB offline phone storage budget while retaining >90% benchmark accuracy.",
        alternatives=["ResNet-50", "EfficientNet-Lite0", "MobileNetV2"],
        status="active",
        decided_by="Rohan Sharma",
        version=1,
    )
    db.add(d17)
    await db.flush()

    # 5. Tasks
    t14 = Task(
        project_id=pid,
        code="T-14",
        title="Quantize MobileNetV3 model to INT8 via TFLite converter",
        status="in_progress",
        owner="Meera Sen",
        priority="high",
        origin_decision_id=d17.id,
        is_blocked=False,
    )
    t15 = Task(
        project_id=pid,
        code="T-15",
        title="Collect supplementary shadow-augmented training dataset",
        status="todo",
        owner="Ananya Patel",
        priority="medium",
        is_blocked=True,
        blocked_reason="Blocked by incomplete upstream task: T-14",
    )
    db.add_all([t14, t15])
    await db.flush()

    # 6. Milestone & Deliverable
    milestone = Milestone(
        project_id=pid,
        name="Milestone 2: Field-Ready Prototype",
        progress_percentage=65,
    )
    db.add(milestone)
    await db.flush()

    deliverable = Deliverable(
        project_id=pid,
        name="LeafGuard Android Demo APK",
        deliverable_type="binary",
        status="in_progress",
        milestone_id=milestone.id,
    )
    db.add(deliverable)
    await db.flush()

    # 7. Contradiction Radar Item
    contradiction = Contradiction(
        project_id=pid,
        claim_a_id=claim_lab.id,
        claim_b_id=claim_field.id,
        detection_method="both",
        status="open",
        explanation="EXP-06 reports 91.2% robust accuracy in benchmark evaluation, but EXP-09 reveals critical field failure at 76.4% under harsh rural lighting conditions.",
    )
    db.add(contradiction)

    # 8. Edges (Graph relations)
    edges = [
        Edge(
            project_id=pid,
            from_type="claim",
            from_id=claim_lab.id,
            to_type="decision",
            to_id=d17.id,
            edge_type="supports",
            rationale_text="91.2% accuracy at 14MB justifies choosing MobileNetV3 over heavy baselines.",
        ),
        Edge(
            project_id=pid,
            from_type="experiment",
            from_id=exp06.id,
            to_type="decision",
            to_id=d17.id,
            edge_type="supports",
            rationale_text="EXP-06 verified memory footprint under 20MB limit.",
        ),
        Edge(
            project_id=pid,
            from_type="experiment_result",
            from_id=res06.id,
            to_type="claim",
            to_id=claim_lab.id,
            edge_type="supports",
        ),
        Edge(
            project_id=pid,
            from_type="decision",
            from_id=d17.id,
            to_type="task",
            to_id=t14.id,
            edge_type="resulted_in",
            rationale_text="D-17 requires int8 quantization for mobile edge runtime.",
        ),
        Edge(
            project_id=pid,
            from_type="task",
            from_id=t14.id,
            to_type="task",
            to_id=t15.id,
            edge_type="depends_on",
            rationale_text="T-15 requires quantization baseline from T-14.",
        ),
        Edge(
            project_id=pid,
            from_type="task",
            from_id=t14.id,
            to_type="deliverable",
            to_id=deliverable.id,
            edge_type="contributes_to",
        ),
    ]
    db.add_all(edges)

    await db.commit()
    return {
        "status": "seeded",
        "project_id": pid,
        "project_name": project.name,
        "message": "Full LeafGuard knowledge graph and demo scenario successfully seeded.",
    }

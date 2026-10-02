from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.entities import (
    Project, Person, Decision, Task, Experiment, ExperimentResult, Claim, Deliverable, Milestone, Contradiction, Edge
)

router = APIRouter(prefix="/seed", tags=["Seed Data"])

@router.post("/demo")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    # Check if existing project exists
    res = await db.execute(select(Project).where(Project.name == "LeafGuard: Edge Crop Disease Detector"))
    existing = res.scalar_one_or_none()
    if existing:
        return {"status": "already_seeded", "project_id": existing.id}

    # 1. Project
    project = Project(
        name="LeafGuard: Edge Crop Disease Detector",
        description="On-device deep learning system for offline crop disease diagnosis in rural farms (KBC 2026 Reference Scenario).",
        notion_parent_id="notion-page-leafguard-root",
    )
    db.add(project)
    await db.flush()

    # 2. Persons
    rohan = Person(project_id=project.id, name="Rohan Sharma", email="rohan@example.com", aliases=["Lead", "Rohan"])
    ananya = Person(project_id=project.id, name="Ananya Patel", email="ananya@example.com", aliases=["Researcher", "Ananya"])
    meera = Person(project_id=project.id, name="Meera Sen", email="meera@example.com", aliases=["ML Eng", "Meera"])
    db.add_all([rohan, ananya, meera])
    await db.flush()

    # 3. Experiments & Results
    exp06 = Experiment(
        project_id=project.id,
        code="EXP-06",
        hypothesis="MobileNetV3 backbone provides sufficient accuracy within the 20MB edge memory envelope.",
        model="MobileNetV3-Small",
        dataset="PlantVillage Clean v2 (14 classes)",
        parameters={"epochs": 50, "batch_size": 32, "lr": 0.001, "quantization": "FP32"},
        status="completed",
        owner="Ananya Patel",
    )
    exp09 = Experiment(
        project_id=project.id,
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
        project_id=project.id,
        experiment_id=exp06.id,
        metric="Top-1 Accuracy",
        value=91.2,
        unit="%",
        split="test",
        source_excerpt="EXP-06 summary: MobileNetV3 + data aug achieved 91.2% top-1 accuracy at 14.1 MB model size."
    )
    res09 = ExperimentResult(
        project_id=project.id,
        experiment_id=exp09.id,
        metric="Top-1 Accuracy",
        value=76.4,
        unit="%",
        split="field_test",
        source_excerpt="EXP-09 field test: Severe degradation under harsh lighting to 76.4% top-1 accuracy."
    )
    db.add_all([res06, res09])
    await db.flush()

    # 4. Claims
    claim_lab = Claim(
        project_id=project.id,
        statement="MobileNetV3 provides 91.2% top-1 accuracy and satisfies the <20MB edge memory budget.",
        claim_type="comparative",
        subject="MobileNetV3",
        metric="Top-1 Accuracy",
        direction="better",
        dataset="PlantVillage",
        status="supported",
        source_excerpt="EXP-06 result R-21: MobileNetV3 achieves 91.2% accuracy at 14 MB vs ResNet50 at 98 MB."
    )
    claim_field = Claim(
        project_id=project.id,
        statement="Field camera samples suffer severe 14.8% accuracy drop due to harsh outdoor lighting variations.",
        claim_type="observation",
        subject="MobileNetV3 Field Reliability",
        metric="Accuracy Drop",
        direction="decrease",
        dataset="Field-MP-500",
        status="unverified",
        source_excerpt="EXP-09: Field images show significant false positives on cassava mosaic disease in bright glare."
    )
    db.add_all([claim_lab, claim_field])
    await db.flush()

    # 5. Decisions
    d17 = Decision(
        project_id=project.id,
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

    # 6. Tasks
    t14 = Task(
        project_id=project.id,
        code="T-14",
        title="Quantize MobileNetV3 model to INT8 via TFLite converter",
        status="in_progress",
        owner="Meera Sen",
        priority="high",
        origin_decision_id=d17.id,
        is_blocked=False,
    )
    t15 = Task(
        project_id=project.id,
        code="T-15",
        title="Collect supplementary shadow-augmented training dataset",
        status="todo",
        owner="Ananya Patel",
        priority="medium",
        is_blocked=False,
    )
    db.add_all([t14, t15])
    await db.flush()

    # 7. Milestone & Deliverable
    milestone = Milestone(
        project_id=project.id,
        name="Milestone 2: Field-Ready Prototype",
        progress_percentage=65,
    )
    db.add(milestone)
    await db.flush()

    deliverable = Deliverable(
        project_id=project.id,
        name="LeafGuard Android Demo APK",
        deliverable_type="binary",
        status="in_progress",
        milestone_id=milestone.id,
    )
    db.add(deliverable)
    await db.flush()

    # 8. Contradiction Radar Item
    contradiction = Contradiction(
        project_id=project.id,
        claim_a_id=claim_lab.id,
        claim_b_id=claim_field.id,
        detection_method="both",
        status="open",
        explanation="EXP-06 reports 91.2% robust accuracy in benchmark evaluation, but EXP-09 reveals critical field failure at 76.4% under harsh rural lighting conditions.",
    )
    db.add(contradiction)

    # 9. Edges (Graph relations)
    edge1 = Edge(
        project_id=project.id,
        from_type="claim",
        from_id=claim_lab.id,
        to_type="decision",
        to_id=d17.id,
        edge_type="supports",
        rationale_text="91.2% accuracy at 14MB justifies choosing MobileNetV3 over heavy baselines.",
    )
    edge2 = Edge(
        project_id=project.id,
        from_type="experiment",
        from_id=exp06.id,
        to_type="decision",
        to_id=d17.id,
        edge_type="supports",
        rationale_text="EXP-06 verified memory footprint under 20MB limit.",
    )
    edge3 = Edge(
        project_id=project.id,
        from_type="decision",
        from_id=d17.id,
        to_type="task",
        to_id=t14.id,
        edge_type="resulted_in",
        rationale_text="D-17 requires int8 quantization for mobile edge runtime.",
    )
    db.add_all([edge1, edge2, edge3])

    await db.commit()
    return {"status": "seeded", "project_id": project.id, "project_name": project.name}

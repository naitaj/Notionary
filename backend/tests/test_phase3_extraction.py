from uuid import uuid4
import os
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import Project, Document, Person, Decision, Task, Experiment, Claim, Proposal, AuditLog, Job
from app.schemas.contracts import (
    ExtractionResult,
    ExtractedDecision,
    ExtractedTask,
    ExtractedClaim,
    ExtractedExperiment,
)
from app.extraction.excerpt_validator import validate_excerpts
from app.extraction.resolvers import resolve_owner, resolve_date
from app.extraction.entity_link import link_entity
from app.extraction.proposal_builder import build_proposals
from workers.runner import process_next_job

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_excerpt_validator_drops_fabricated():
    """
    Plan §3.3 & §4.2: Excerpts must match verbatim or >=90% rapidfuzz in source text.
    Hallucinated / fabricated excerpts must be discarded and logged.
    """
    source_text = (
        "Meeting: LeafGuard Core Architecture Review (M-04)\n"
        "Decision D-17: Adopt MobileNetV3-Small as the edge inference architecture.\n"
        "Ananya Patel: I will take on task T-14: Quantize MobileNetV3-Small to INT8.\n"
    )

    result = ExtractionResult(
        document_id="doc-123",
        doc_type="meeting_note",
        decisions=[
            ExtractedDecision(
                code="D-17",
                statement="Adopt MobileNetV3-Small",
                excerpt="Decision D-17: Adopt MobileNetV3-Small as the edge inference architecture."
            ),
            ExtractedDecision(
                code="D-99",
                statement="Fabricated decision that was hallucinated",
                excerpt="This sentence never appeared in the source text at all."
            )
        ],
        tasks=[
            ExtractedTask(
                code="T-14",
                title="Quantize MobileNetV3-Small",
                excerpt="take on task T-14: Quantize MobileNetV3-Small to INT8."
            ),
            ExtractedTask(
                code="T-99",
                title="Fabricated task",
                excerpt="Completely fake excerpt injected by malicious prompt."
            )
        ],
        experiments=[],
        claims=[]
    )

    validated = validate_excerpts(result, source_text)

    # Valid items preserved
    assert len(validated.decisions) == 1
    assert validated.decisions[0].code == "D-17"
    assert len(validated.tasks) == 1
    assert validated.tasks[0].code == "T-14"

    # Fabricated items dropped and counted
    assert validated.discarded_excerpts_count == 2

@pytest.mark.asyncio
async def test_resolvers_owner_and_date():
    """
    Plan §3.4: Fuzzy match owner to people.aliases / display_name,
    and parse relative dates.
    """
    async with AsyncSessionLocal() as session:
        proj_id = f"test-proj-res-{uuid4().hex[:8]}"
        proj = Project(id=proj_id, name="Resolver Test Project")
        session.add(proj)

        p1 = Person(
            project_id=proj_id,
            display_name="Karan Mehta",
            aliases=["Karan", "karan@leafguard.ai"]
        )
        p2 = Person(
            project_id=proj_id,
            display_name="Ananya Patel",
            aliases=["Ananya", "ananya@leafguard.ai"]
        )
        session.add_all([p1, p2])
        await session.commit()

        # Match alias
        matched_id1 = await resolve_owner(session, proj_id, "Karan")
        assert matched_id1 == p1.id

        # Match display name fuzzy
        matched_id2 = await resolve_owner(session, proj_id, "Ananya Patel")
        assert matched_id2 == p2.id

        # Unknown person
        matched_none = await resolve_owner(session, proj_id, "Unknown Outsider")
        assert matched_none is None

    # Date resolution
    meeting_date = datetime(2026, 3, 15, tzinfo=timezone.utc)
    res_date = resolve_date("2026-03-25", meeting_date)
    assert res_date is not None
    assert res_date.year == 2026 and res_date.month == 3 and res_date.day == 25

@pytest.mark.asyncio
async def test_entity_linking_no_auto_merge():
    """
    Plan §3.5: Exact code match -> link (without auto-merging).
    High similarity -> flag as needs_attention.
    """
    async with AsyncSessionLocal() as session:
        proj_id = f"test-proj-link-{uuid4().hex[:8]}"
        proj = Project(id=proj_id, name="Linking Test Project")
        session.add(proj)

        exp = Experiment(
            project_id=proj_id,
            code="EXP-06",
            hypothesis="MobileNetV3 benchmark vs ResNet-18"
        )
        dec = Decision(
            project_id=proj_id,
            code="D-12",
            statement="Use ResNet-18 architecture for edge evaluation"
        )
        session.add_all([exp, dec])
        await session.commit()

        # Exact code match
        link_id, needs_att = await link_entity(session, proj_id, "experiment", "EXP-06", "")
        assert link_id == exp.id
        assert needs_att is False

        # Similar statement (possible update) -> needs_attention
        link_id2, needs_att2 = await link_entity(
            session, proj_id, "decision", None,
            "Use ResNet-18 architecture for edge evaluation"
        )
        assert link_id2 == dec.id
        assert needs_att2 is True

        # Brand new code/text
        link_id3, needs_att3 = await link_entity(session, proj_id, "task", "T-999", "Completely new task")
        assert link_id3 is None
        assert needs_att3 is False

@pytest.mark.asyncio
async def test_proposals_api_and_review_lifecycle():
    """
    Plan §3.6, §3.7, §3.8:
    - Proposals created with tiers (high for decisions, medium for tasks/claims/experiments)
    - List proposals via GET /api/v1/proposals
    - PATCH proposal payload
    - Bulk-approve blocks high-tier items
    - Individual approve creates entity + audit log + enqueues notion push
    - Reject stores rejection reason
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_id = f"proj-prop-{uuid4().hex[:8]}"
        async with AsyncSessionLocal() as session:
            proj = Project(id=proj_id, name="Proposal Lifecycle Project")
            session.add(proj)

            # Create test proposals
            p_high = Proposal(
                project_id=proj_id,
                entity_type="decision",
                tier="high",
                confidence_label="high",
                needs_attention=False,
                status="pending",
                payload={"code": "D-17", "statement": "Adopt MobileNetV3-Small", "rationale": "High efficiency"},
            )
            p_med = Proposal(
                project_id=proj_id,
                entity_type="task",
                tier="medium",
                confidence_label="high",
                needs_attention=False,
                status="pending",
                payload={"code": "T-14", "title": "Quantize MobileNetV3-Small"},
            )
            p_reject = Proposal(
                project_id=proj_id,
                entity_type="claim",
                tier="medium",
                confidence_label="low",
                needs_attention=True,
                status="pending",
                payload={"statement": "Questionable claim to reject"},
            )
            session.add_all([p_high, p_med, p_reject])
            await session.commit()
            p_high_id = p_high.id
            p_med_id = p_med.id
            p_reject_id = p_reject.id

        # 1. List proposals
        res = await client.get(f"/api/v1/proposals/?project_id={proj_id}&status=pending")
        assert res.status_code == 200
        proposals_list = res.json()
        assert len(proposals_list) == 3

        # 2. PATCH proposal payload
        patch_res = await client.patch(
            f"/api/v1/proposals/{p_med_id}",
            json={"code": "T-14", "title": "Quantize MobileNetV3-Small to INT8 via TensorRT"}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["payload"]["title"] == "Quantize MobileNetV3-Small to INT8 via TensorRT"

        # 3. Bulk-approve high-tier proposal must be rejected (Plan §3.6 & §3.7)
        bulk_fail_res = await client.post(
            "/api/v1/proposals/bulk-approve",
            json={"project_id": proj_id, "proposal_ids": [p_high_id, p_med_id]}
        )
        assert bulk_fail_res.status_code == 400
        assert "Cannot bulk approve high tier" in bulk_fail_res.json()["detail"]

        # 4. Individual approve high-tier proposal
        approve_res = await client.post(f"/api/v1/proposals/{p_high_id}/approve")
        assert approve_res.status_code == 200

        # Verify Decision created, Proposal marked approved, and AuditLog created
        async with AsyncSessionLocal() as session:
            dec = (await session.execute(
                select(Decision).where(Decision.project_id == proj_id, Decision.code == "D-17")
            )).scalars().first()
            assert dec is not None
            assert dec.statement == "Adopt MobileNetV3-Small"
            assert dec.origin == "system_derived"

            audit = (await session.execute(
                select(AuditLog).where(AuditLog.project_id == proj_id, AuditLog.entity_id == dec.id)
            )).scalars().first()
            assert audit is not None
            assert audit.action == "approve_proposal"

            prop = (await session.execute(
                select(Proposal).where(Proposal.id == p_high_id)
            )).scalars().first()
            assert prop.status == "approved"

        # 5. Bulk-approve medium tier proposal
        bulk_ok_res = await client.post(
            "/api/v1/proposals/bulk-approve",
            json={"project_id": proj_id, "proposal_ids": [p_med_id]}
        )
        assert bulk_ok_res.status_code == 200
        assert bulk_ok_res.json()["count"] == 1

        # 6. Reject proposal with reason
        reject_res = await client.post(
            f"/api/v1/proposals/{p_reject_id}/reject",
            json={"reason": "Insufficient evidence in meeting transcript"}
        )
        assert reject_res.status_code == 200
        async with AsyncSessionLocal() as session:
            rejected_prop = (await session.execute(
                select(Proposal).where(Proposal.id == p_reject_id)
            )).scalars().first()
            assert rejected_prop.status == "rejected"
            assert rejected_prop.rejection_reason == "Insufficient evidence in meeting transcript"

@pytest.mark.asyncio
async def test_end_to_end_extraction_worker():
    """
    Plan §3: Ingesting meeting note triggers extraction job, produces proposals in review inbox.
    """
    async with AsyncSessionLocal() as session:
        proj_id = f"proj-m04-{uuid4().hex[:8]}"
        proj = Project(id=proj_id, name="M-04 Extraction Project")
        session.add(proj)

        # Read fixture
        test_dir = os.path.dirname(os.path.abspath(__file__))
        m04_path = os.path.join(test_dir, "../../fixtures/leafguard/M-04.txt")
        if not os.path.exists(m04_path):
            m04_path = os.path.join(test_dir, "../fixtures/leafguard/M-04.txt")
        with open(m04_path, "r", encoding="utf-8") as f:
            content = f.read()

        doc = Document(
            project_id=proj_id,
            title="Meeting M-04",
            doc_type="meeting_note",
            content_text=content,
            pipeline_status="chunked"
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

        # Enqueue extraction job
        job = Job(
            project_id=proj_id,
            job_type="extraction",
            payload={"document_id": doc_id},
            status="queued"
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    # Execute extraction job via worker
    executed = await process_next_job(worker_id="test-worker", job_id=job_id)
    assert executed is True

    async with AsyncSessionLocal() as session:
        # Check job succeeded
        executed_job = (await session.execute(
            select(Job).where(Job.id == job_id)
        )).scalars().first()
        assert executed_job.status == "succeeded"

        # Check document marked extracted
        extracted_doc = (await session.execute(
            select(Document).where(Document.id == doc_id)
        )).scalars().first()
        assert extracted_doc.pipeline_status == "extracted"

        # Check proposals were created
        proposals = (await session.execute(
            select(Proposal).where(Proposal.project_id == proj_id)
        )).scalars().all()
        assert len(proposals) > 0

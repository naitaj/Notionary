from uuid import uuid4
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import (
    Project, Document, Chunk, Decision, Task, Experiment, ExperimentResult, Claim, Edge, Contradiction, EvalRun
)
from app.core.auth import UserScope
from app.rag.permissions import get_visibility_filter, filter_query_by_scope
from app.rag.intent import detect_query_intent
from app.rag.expansion import expand_graph_context
from app.rag.context import assemble_rag_context
from app.rag.citation_validator import validate_citations_and_refusal, REFUSAL_TEXT
from app.rag.retrieval import perform_rag_retrieval, RetrievedContextItem
from app.rag.eval import run_golden_qa_eval

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_permission_filter_prevents_guest_access_to_team_chunks():
    """
    Plan §4.1: Permission filter first.
    A guest query must strictly NEVER retrieve team-scoped or private documents/chunks.
    """
    project_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        proj = Project(id=project_id, name="Security Test Project")
        db.add(proj)

        # 1. Public document
        doc_public = Document(
            id=str(uuid4()),
            project_id=project_id,
            title="DOC-PUBLIC: General Architecture",
            doc_type="design_doc",
            visibility="project",
            origin="human_authored",
        )
        db.add(doc_public)

        chunk_public = Chunk(
            id=str(uuid4()),
            project_id=project_id,
            document_id=doc_public.id,
            heading_path="Overview",
            char_start=0,
            char_end=100,
            text="This is a publicly visible architecture overview document.",
            embedding=[0.1] * 384,
        )
        db.add(chunk_public)

        # 2. Team-restricted document
        doc_team = Document(
            id=str(uuid4()),
            project_id=project_id,
            title="DOC-RESTRICTED: Internal ML Weights & Secret Specs",
            doc_type="design_doc",
            visibility="team",
            visibility_team_id="team_classified",
            origin="human_authored",
        )
        db.add(doc_team)

        chunk_team = Chunk(
            id=str(uuid4()),
            project_id=project_id,
            document_id=doc_team.id,
            heading_path="Secrets",
            char_start=0,
            char_end=120,
            text="Proprietary confidential training hyper-parameters and unreleased security tokens.",
            embedding=[0.2] * 384,
        )
        db.add(chunk_team)
        await db.commit()

        # Test Guest Scope
        guest_scope = UserScope(
            user_id="usr_guest_tester",
            project_id=project_id,
            role="guest",
            team_ids=[],
        )

        intent = detect_query_intent("architecture and secret parameters")
        guest_results = await perform_rag_retrieval(
            db=db,
            project_id=project_id,
            query="architecture and secret parameters",
            scope=guest_scope,
            intent=intent,
            top_k=10,
        )

        retrieved_ids = [item.id for item in guest_results]
        retrieved_titles = [item.code_or_title for item in guest_results]

        assert chunk_public.id in retrieved_ids, "Guest should be able to view public chunk"
        assert chunk_team.id not in retrieved_ids, "SECURITY VIOLATION: Guest retrieved team-scoped chunk!"
        for title in retrieved_titles:
            assert "Secret" not in title, "SECURITY VIOLATION: Guest saw title of team-restricted document!"

        # Test Member Scope with appropriate team access
        member_scope = UserScope(
            user_id="usr_member_tester",
            project_id=project_id,
            role="member",
            team_ids=["team_classified"],
        )

        member_results = await perform_rag_retrieval(
            db=db,
            project_id=project_id,
            query="architecture and secret parameters",
            scope=member_scope,
            intent=intent,
            top_k=10,
        )

        member_retrieved_ids = [item.id for item in member_results]
        assert chunk_public.id in member_retrieved_ids
        assert chunk_team.id in member_retrieved_ids, "Authorized team member must retrieve team chunk"

@pytest.mark.asyncio
async def test_intent_and_entity_detection():
    """
    Plan §4.2: Intent/entity detection parses entity codes, aliases, and categories.
    """
    q1 = "Why was Model B (MobileNetV3) chosen in D-17 instead of Model A?"
    intent1 = detect_query_intent(q1)
    assert intent1.intent_type == "decision"
    assert "D-17" in intent1.entity_codes
    assert "MobileNetV3" in intent1.model_aliases

    q2 = "What were the accuracy and latency metrics in benchmark EXP-06?"
    intent2 = detect_query_intent(q2)
    assert intent2.intent_type == "experiment"
    assert "EXP-06" in intent2.entity_codes

    q3 = "Who is assigned to task T-14 and when is it due?"
    intent3 = detect_query_intent(q3)
    assert intent3.intent_type == "task"
    assert "T-14" in intent3.entity_codes

@pytest.mark.asyncio
async def test_graph_expansion_with_restricted_placeholders():
    """
    Plan §4.4: Graph expansion (1-2 hops). Nodes outside user's permission scope
    must become restricted placeholders (type + existence only) without leaking titles or content.
    """
    project_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        dec = Decision(
            id=str(uuid4()),
            project_id=project_id,
            code="D-17",
            statement="Adopt MobileNetV3 for edge deployment",
            visibility="project",
            origin="human_authored",
        )
        db.add(dec)

        # Team restricted task
        secret_task = Task(
            id=str(uuid4()),
            project_id=project_id,
            code="T-99",
            title="Classified Hardware Bypass Implementation",
            visibility="team",
            visibility_team_id="stealth_team",
            origin="human_authored",
        )
        db.add(secret_task)

        # Edge from D-17 to T-99
        edge = Edge(
            id=str(uuid4()),
            project_id=project_id,
            from_type="decision",
            from_id=dec.id,
            to_type="task",
            to_id=secret_task.id,
            edge_type="resulted_in",
            origin="human_authored",
            review_status="approved",
        )
        db.add(edge)
        await db.commit()

        # Seed item
        seed_item = RetrievedContextItem(
            id=dec.id,
            entity_type="decision",
            code_or_title="Decision D-17",
            text_content=dec.statement,
        )

        guest_scope = UserScope(
            user_id="usr_auditor",
            project_id=project_id,
            role="guest",
            team_ids=[],
        )

        graph_nodes, add_items = await expand_graph_context(
            db=db,
            project_id=project_id,
            seed_items=[seed_item],
            scope=guest_scope,
            max_hops=1,
        )

        assert len(graph_nodes) == 1
        placeholder = graph_nodes[0]
        assert placeholder.is_restricted is True, "Out of scope neighbor must be flagged as restricted"
        assert placeholder.code is None, "Restricted placeholder must not leak code"
        assert "Restricted" in placeholder.title, "Placeholder title must indicate restricted status"
        assert "Classified" not in placeholder.title, "Restricted placeholder must not leak sensitive title"
        assert len(add_items) == 0, "Restricted content must never be added to context items"

@pytest.mark.asyncio
async def test_citation_validator_rejects_hallucinations_and_triggers_refusal():
    """
    Plan §4.6: Strict citation validation.
    Every [n] must resolve to supplied context; invalid citations trigger refusal.
    """
    from app.schemas.contracts import Citation

    citation_map = {
        1: Citation(
            citation_number=1,
            entity_type="decision",
            entity_id="d-1",
            code_or_title="Decision D-17",
            excerpt="Adopt MobileNetV3-Small",
        )
    }

    # Valid answer citing [1]
    valid_ans = "We adopted MobileNetV3 as our edge model [1]."
    ok, citations, reason = validate_citations_and_refusal(valid_ans, citation_map)
    assert ok is True
    assert len(citations) == 1
    assert citations[0].citation_number == 1

    # Hallucinated answer citing [99] which doesn't exist in citation_map
    hallucinated_ans = "We adopted MobileNetV3 because of superior accuracy [99]."
    ok, _, reason = validate_citations_and_refusal(hallucinated_ans, citation_map)
    assert ok is False
    assert "99" in str(reason)

    # Empty context must trigger refusal
    ok, _, reason = validate_citations_and_refusal("Some answer [1].", {})
    assert ok is False

@pytest.mark.asyncio
async def test_end_to_end_rag_query_with_contradiction_flagging():
    """
    Plan §4.7: POST /api/v1/ai/query returns grounded answer, verified citations,
    and flags open contradictions touching the entities.
    """
    project_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        dec = Decision(
            id=str(uuid4()),
            project_id=project_id,
            code="D-17",
            statement="Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            rationale="MobileNetV3 meets our 20ms latency ceiling and offline 20MB budget.",
            visibility="project",
            origin="human_authored",
            decided_on=datetime.now(timezone.utc),
        )
        db.add(dec)

        exp = Experiment(
            id=str(uuid4()),
            project_id=project_id,
            code="EXP-06",
            model="MobileNetV3-Small",
            dataset="PlantVillage Clean v2",
            hypothesis="MobileNetV3 satisfies edge latency and accuracy envelope",
            visibility="project",
            origin="system_derived",
        )
        db.add(exp)

        exp_res = ExperimentResult(
            id=str(uuid4()),
            project_id=project_id,
            experiment_id=exp.id,
            metric="accuracy",
            value=91.2,
            unit="%",
            visibility="project",
            origin="system_derived",
        )
        db.add(exp_res)

        # Open contradiction for field degradation
        contra = Contradiction(
            id=str(uuid4()),
            project_id=project_id,
            a_type="experiment_result",
            a_id=exp_res.id,
            b_type="claim",
            b_id=str(uuid4()),
            status="open",
            explanation="EXP-09 field test (76.4% top-1 accuracy) contradicts EXP-06 benchmark (91.2%) under direct sunlight glare.",
        )
        db.add(contra)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/ai/query",
            json={
                "project_id": project_id,
                "query": "Why was Model B (MobileNetV3) chosen over Model A in Decision D-17?",
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["refusal"] is False
        assert len(data["answer"]) > 10
        assert len(data["citations"]) > 0
        # Check computed fields for frontend backwards-compatibility
        assert "n" in data["citations"][0]
        assert "record" in data["citations"][0]
        assert "provenance_bar" in data
        assert len(data["open_contradictions_flagged"]) > 0
        assert "sunlight" in data["open_contradictions_flagged"][0].lower()

@pytest.mark.asyncio
async def test_golden_qa_eval_runner():
    """
    Plan §4.9: Golden Q&A evaluation benchmark.
    Tests the 10 golden test cases and verifies hit@5 >= 0.8 and citation correctness.
    """
    project_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        # Seed core project entities so golden questions have evidence
        d17 = Decision(
            id=str(uuid4()),
            project_id=project_id,
            code="D-17",
            statement="Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
            rationale="Selected over ResNet-18 (31.8ms latency, too large) and MobileNetV2 to satisfy 20ms latency and 20MB budget.",
            alternatives=[{"name": "ResNet-18", "reason": "31.8ms latency violates 20ms constraint"}, {"name": "MobileNetV2", "reason": "Higher memory footprint"}],
            visibility="project",
            origin="human_authored",
        )
        db.add(d17)

        exp06 = Experiment(
            id=str(uuid4()),
            project_id=project_id,
            code="EXP-06",
            model="MobileNetV3-Small",
            dataset="PlantVillage Clean v2",
            hypothesis="MobileNetV3 achieves 91.2% accuracy within 20ms latency",
            visibility="project",
            origin="system_derived",
        )
        db.add(exp06)

        r21 = ExperimentResult(
            id=str(uuid4()),
            project_id=project_id,
            experiment_id=exp06.id,
            metric="accuracy",
            value=91.2,
            unit="%",
            visibility="project",
            origin="system_derived",
        )
        db.add(r21)

        t14 = Task(
            id=str(uuid4()),
            project_id=project_id,
            code="T-14",
            title="Quantize MobileNetV3-Small to INT8 via TensorRT-LLM",
            owner="Ananya Patel",
            status="in_progress",
            priority="high",
            visibility="project",
            origin="human_authored",
        )
        db.add(t14)

        t15 = Task(
            id=str(uuid4()),
            project_id=project_id,
            code="T-15",
            title="Integrate MobileNetV3-Small into Android camera capture daemon",
            owner="Vikram",
            status="todo",
            priority="medium",
            visibility="project",
            origin="human_authored",
        )
        db.add(t15)

        doc05 = Document(
            id=str(uuid4()),
            project_id=project_id,
            title="DOC-05: Server Architecture & Edge Deployment Spec",
            doc_type="design_doc",
            visibility="project",
            origin="human_authored",
        )
        db.add(doc05)

        chunk05 = Chunk(
            id=str(uuid4()),
            project_id=project_id,
            document_id=doc05.id,
            heading_path="Hardware Envelope",
            char_start=0,
            char_end=200,
            text="The edge hardware envelope strictly limits inference latency to 20ms and memory to 20MB offline storage.",
            embedding=[0.05] * 384,
        )
        db.add(chunk05)

        contra = Contradiction(
            id=str(uuid4()),
            project_id=project_id,
            a_type="experiment",
            a_id=exp06.id,
            b_type="claim",
            b_id=str(uuid4()),
            status="open",
            explanation="Field evaluation EXP-09 showed accuracy degradation to 76.4% under harsh direct sunlight glare.",
        )
        db.add(contra)
        await db.commit()

        # Run golden Q&A evaluation
        eval_run = await run_golden_qa_eval(db=db, project_id=project_id)

        assert eval_run.total_cases == 10
        assert eval_run.hit_at_5 >= 0.8, f"Hit@5 was {eval_run.hit_at_5}, expected >= 0.8"
        assert eval_run.passed_cases >= 8, f"Passed {eval_run.passed_cases}/10 cases, expected >= 8"

        # Verify saved in DB
        db_eval = await db.get(EvalRun, eval_run.id)
        assert db_eval is not None
        assert db_eval.total_cases == 10

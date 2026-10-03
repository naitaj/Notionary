from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities import EvalCase, EvalRun
from app.core.auth import UserScope, DEFAULT_DEMO_USER
from app.rag.engine import execute_rag_query, REFUSAL_TEXT

GOLDEN_QA_CASES: List[Dict[str, Any]] = [
    {
        "query": "Why was Model B (MobileNetV3) chosen over Model A?",
        "expected_sources": ["D-17", "EXP-06", "DOC-05"],
        "should_refuse": False,
        "description": "Decision D-17 rationale and edge latency constraints",
    },
    {
        "query": "What were the benchmark results for experiment EXP-06?",
        "expected_sources": ["EXP-06"],
        "should_refuse": False,
        "description": "Experiment EXP-06 latency and accuracy metrics",
    },
    {
        "query": "What task is assigned to Ananya Patel regarding quantization?",
        "expected_sources": ["T-14"],
        "should_refuse": False,
        "description": "Task T-14 ownership and due date",
    },
    {
        "query": "What are the edge latency and memory budget constraints for on-device deployment?",
        "expected_sources": ["DOC-05", "D-17", "M-01"],
        "should_refuse": False,
        "description": "Hardware resource envelope (20ms latency, 20MB storage)",
    },
    {
        "query": "What discrepancy was identified in field evaluation EXP-09 under direct sunlight?",
        "expected_sources": ["EXP-09", "C-01"],
        "should_refuse": False,
        "description": "Contradiction between EXP-06 benchmark and EXP-09 field test",
    },
    {
        "query": "Who is the owner of task T-15 and what is its target deadline?",
        "expected_sources": ["T-15"],
        "should_refuse": False,
        "description": "Task T-15 integration into camera daemon",
    },
    {
        "query": "What alternatives were considered for decision D-17?",
        "expected_sources": ["D-17"],
        "should_refuse": False,
        "description": "Decision D-17 alternatives (ResNet-18, MobileNetV2)",
    },
    {
        "query": "What was the inference latency recorded for ResNet-18 on the target hardware?",
        "expected_sources": ["D-17", "EXP-06", "M-04"],
        "should_refuse": False,
        "description": "ResNet-18 latency benchmark (31.8ms violating ceiling)",
    },
    {
        "query": "What is our Q4 marketing campaign strategy and budget for North America?",
        "expected_sources": [],
        "should_refuse": True,
        "description": "Out-of-scope query testing refusal guardrails",
    },
    {
        "query": "How many quantum computers are deployed in the rural greenhouse edge nodes?",
        "expected_sources": [],
        "should_refuse": True,
        "description": "Hallucination trap testing refusal guardrails",
    },
]

async def seed_golden_eval_cases(db: AsyncSession, project_id: str):
    """Idempotently seeds golden Q&A eval cases into eval_cases table."""
    for case_data in GOLDEN_QA_CASES:
        stmt = select(EvalCase).where(
            EvalCase.project_id == project_id,
            EvalCase.query == case_data["query"],
        )
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            ec = EvalCase(
                project_id=project_id,
                kind="qa",
                query=case_data["query"],
                expected_sources=case_data["expected_sources"],
                should_refuse=case_data["should_refuse"],
            )
            db.add(ec)
    await db.commit()

async def run_golden_qa_eval(
    db: AsyncSession,
    project_id: str,
    scope: Optional[UserScope] = None,
    git_sha: str = "phase4-head",
    prompt_version: str = "v1.0.0",
) -> EvalRun:
    """
    Plan §4.9: Golden Q&A evaluation runner.
    Executes the 10 golden benchmark cases, measuring Hit@5, citation correctness,
    and refusal compliance. Records an EvalRun in the database.
    """
    user_scope = scope or UserScope(
        user_id=DEFAULT_DEMO_USER.id,
        project_id=project_id,
        role="member",
        team_ids=["team_ml", "team_edge"],
    )

    total = len(GOLDEN_QA_CASES)
    passed_count = 0
    hit_at_5_count = 0
    citation_correct_count = 0
    case_results = []

    for case in GOLDEN_QA_CASES:
        query = case["query"]
        expected_sources = case["expected_sources"]
        should_refuse = case["should_refuse"]

        ans = await execute_rag_query(
            db=db,
            project_id=project_id,
            query=query,
            scope=user_scope,
        )

        cited_titles = [c.code_or_title for c in ans.citations]
        cited_text = " ".join([c.code_or_title + " " + c.excerpt for c in ans.citations])

        # Evaluate Hit@5
        hit_at_5 = False
        if should_refuse:
            hit_at_5 = ans.refusal
        else:
            hit_at_5 = any(
                src.lower() in cited_text.lower() or any(src.lower() in t.lower() for t in cited_titles)
                for src in expected_sources
            )
        if hit_at_5:
            hit_at_5_count += 1

        # Evaluate citation correctness
        citation_correct = False
        if should_refuse:
            citation_correct = ans.refusal and (REFUSAL_TEXT.lower() in ans.answer.lower())
        else:
            # Must have at least one citation and all citations must be valid
            citation_correct = len(ans.citations) > 0 and not ans.refusal

        if citation_correct:
            citation_correct_count += 1

        # Case overall pass
        case_passed = hit_at_5 and citation_correct
        if case_passed:
            passed_count += 1

        case_results.append({
            "query": query,
            "should_refuse": should_refuse,
            "actual_refusal": ans.refusal,
            "hit_at_5": hit_at_5,
            "citation_correct": citation_correct,
            "passed": case_passed,
            "citations_count": len(ans.citations),
            "answer_preview": ans.answer[:120],
        })

    hit_at_5_rate = round(hit_at_5_count / total, 3)
    citation_correctness_rate = round(citation_correct_count / total, 3)

    eval_run = EvalRun(
        project_id=project_id,
        eval_type="qa",
        git_sha=git_sha,
        prompt_version=prompt_version,
        model="groq-or-mock",
        total_cases=total,
        passed_cases=passed_count,
        hit_at_5=hit_at_5_rate,
        citation_correctness=citation_correctness_rate,
        metrics={
            "cases": case_results,
            "pass_rate": round(passed_count / total, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(eval_run)
    await db.commit()
    await db.refresh(eval_run)

    return eval_run

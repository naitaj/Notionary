"""
Phase 8 — Missing-Evidence Detector & Claim Coverage Engine (PRD §14.4 / Plan §8.2)

Evaluates checklist-based sufficiency profiles for evaluative and empirical claims.
Taxonomy:
  - well_supported: >=1 linked evidence meeting sufficiency checklist, no open contradiction, not stale
  - partially_supported: evidence linked but checklist incomplete
  - unsupported: no evidence edge
  - potentially_contradicted: >=1 open contradiction
  - potentially_stale: source document/decision superseded or flagged stale
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.entities import (
    Claim, Edge, ExperimentResult, Experiment, Document, Contradiction, StaleFlag, Decision
)
from app.schemas.contracts import CoverageResult, CoverageCheckItem

# Canonical checklist items for evaluative/empirical claims
CHECKLIST_DEFINITIONS = [
    {
        "dimension": "comparison_baseline",
        "description": "Baseline reference or comparator specified",
        "missing_label": "no baseline comparison",
    },
    {
        "dimension": "metric_value",
        "description": "Concrete metric and quantified value provided",
        "missing_label": "no metric value",
    },
    {
        "dimension": "dataset_named",
        "description": "Evaluation dataset or test benchmark named",
        "missing_label": "no dataset named",
    },
    {
        "dimension": "sample_size_runs",
        "description": "Number of runs or sample size reported (>1 run)",
        "missing_label": "no run count",
    },
    {
        "dimension": "variance_or_statistical_test",
        "description": "Variance, standard deviation, or confidence interval reported",
        "missing_label": "no variance reported",
    },
]


async def evaluate_claim_coverage(
    db: AsyncSession,
    claim: Claim,
    edges: Optional[List[Edge]] = None,
    contradictions: Optional[List[Contradiction]] = None,
    stale_flags: Optional[List[StaleFlag]] = None,
) -> CoverageResult:
    """Evaluate sufficiency checklist and taxonomy status for a single claim."""
    # 1. Fetch incoming evidence edges (supports / based_on / validates)
    if edges is None:
        edge_res = await db.execute(
            select(Edge).where(
                Edge.to_id == claim.id,
                Edge.effective_to.is_(None),
                Edge.edge_type.in_(["supports", "validates", "based_on", "motivates"]),
            )
        )
        incoming_edges = edge_res.scalars().all()
    else:
        incoming_edges = [
            e for e in edges
            if e.to_id == claim.id and e.edge_type in ("supports", "validates", "based_on", "motivates")
        ]

    # 2. Fetch contradictions
    if contradictions is None:
        contra_res = await db.execute(
            select(Contradiction).where(
                Contradiction.project_id == claim.project_id,
                Contradiction.status == "open",
                or_(
                    Contradiction.a_id == claim.id,
                    Contradiction.b_id == claim.id,
                ),
            )
        )
        open_contras = contra_res.scalars().all()
    else:
        open_contras = [
            c for c in contradictions
            if c.status == "open" and (c.a_id == claim.id or c.b_id == claim.id)
        ]

    # 3. Check staleness
    is_stale = False
    if claim.document_id:
        if stale_flags is None:
            sf_res = await db.execute(
                select(StaleFlag).where(
                    StaleFlag.document_id == claim.document_id,
                    StaleFlag.status == "active",
                )
            )
            is_stale = sf_res.scalar_one_or_none() is not None
        else:
            is_stale = any(sf.document_id == claim.document_id and sf.status == "active" for sf in stale_flags)

    # 4. Fetch linked results / experiments if any
    linked_result_ids = [e.from_id for e in incoming_edges if e.from_type == "experiment_result"]
    linked_results: List[ExperimentResult] = []
    if linked_result_ids:
        r_res = await db.execute(
            select(ExperimentResult).where(ExperimentResult.id.in_(linked_result_ids))
        )
        linked_results = r_res.scalars().all()

    # 5. Evaluate sufficiency checklist
    checklist_items: List[CoverageCheckItem] = []
    missing_labels: List[str] = []

    # Baseline present?
    has_baseline = (
        bool(claim.condition and ("vs" in claim.condition.lower() or "baseline" in claim.condition.lower()))
        or ("better than" in claim.statement.lower() or "vs " in claim.statement.lower())
        or any(bool(r.baseline_ref) for r in linked_results)
    )
    if has_baseline:
        checklist_items.append(CoverageCheckItem(
            dimension="comparison_baseline",
            description="Baseline reference or comparator specified",
            status="satisfied",
            details="Baseline comparison specified in evidence or claim statement",
        ))
    else:
        checklist_items.append(CoverageCheckItem(
            dimension="comparison_baseline",
            description="Baseline reference or comparator specified",
            status="missing",
            details="No baseline reference found",
        ))
        missing_labels.append("no baseline comparison")

    # Metric & value present?
    has_metric_value = (
        (claim.metric is not None and claim.value is not None)
        or any(r.value is not None for r in linked_results)
    )
    if has_metric_value:
        checklist_items.append(CoverageCheckItem(
            dimension="metric_value",
            description="Concrete metric and quantified value provided",
            status="satisfied",
            details=f"Metric: {claim.metric or 'linked'}, Value: {claim.value or (linked_results[0].value if linked_results else 'present')}",
        ))
    else:
        checklist_items.append(CoverageCheckItem(
            dimension="metric_value",
            description="Concrete metric and quantified value provided",
            status="missing",
            details="Neither claim nor linked results contain a concrete numeric value",
        ))
        missing_labels.append("no metric value")

    # Dataset named?
    has_dataset = bool(claim.dataset) or any(bool(r.split) for r in linked_results)
    if has_dataset:
        checklist_items.append(CoverageCheckItem(
            dimension="dataset_named",
            description="Evaluation dataset or test benchmark named",
            status="satisfied",
            details=f"Dataset: {claim.dataset or 'specified in results'}",
        ))
    else:
        checklist_items.append(CoverageCheckItem(
            dimension="dataset_named",
            description="Evaluation dataset or test benchmark named",
            status="missing",
            details="No benchmark dataset named",
        ))
        missing_labels.append("no dataset named")

    # Sample size / runs reported (>1)?
    has_runs = any(r.num_runs and r.num_runs > 1 for r in linked_results)
    if has_runs:
        checklist_items.append(CoverageCheckItem(
            dimension="sample_size_runs",
            description="Number of runs or sample size reported (>1 run)",
            status="satisfied",
            details=f"Multiple runs recorded ({max(r.num_runs for r in linked_results if r.num_runs)} runs)",
        ))
    else:
        checklist_items.append(CoverageCheckItem(
            dimension="sample_size_runs",
            description="Number of runs or sample size reported (>1 run)",
            status="missing",
            details="Single run or run count unspecified (1 run)",
        ))
        missing_labels.append("no run count")

    # Variance or statistical test reported?
    has_variance = any(r.variance is not None for r in linked_results)
    if has_variance:
        checklist_items.append(CoverageCheckItem(
            dimension="variance_or_statistical_test",
            description="Variance, standard deviation, or confidence interval reported",
            status="satisfied",
            details="Variance or standard deviation present in experiment result",
        ))
    else:
        checklist_items.append(CoverageCheckItem(
            dimension="variance_or_statistical_test",
            description="Variance, standard deviation, or confidence interval reported",
            status="missing",
            details="No variance, standard deviation, or statistical test provided",
        ))
        missing_labels.append("no variance reported")

    # 6. Determine taxonomy status (PRD §14.4)
    # Order of priority:
    # 1. potentially_contradicted
    # 2. potentially_stale
    # 3. unsupported (if no incoming evidence edge)
    # 4. partially_supported (if evidence linked but checklist missing items)
    # 5. well_supported (if evidence linked and all checklist items satisfied)
    if len(open_contras) > 0:
        taxonomy = "potentially_contradicted"
        badge_text = "Potentially contradicted by field findings"
        coverage_status = "contradicted"
        summary_verdict = f"Flagged by Contradiction Radar: {len(open_contras)} open discrepancy found."
    elif is_stale:
        taxonomy = "potentially_stale"
        badge_text = "Potentially stale source document"
        coverage_status = "stale"
        summary_verdict = "Source document or originating context has been superseded or flagged stale."
    elif len(incoming_edges) == 0:
        taxonomy = "unsupported"
        badge_text = "Unsupported (no linked evidence)"
        coverage_status = "missing_evidence"
        summary_verdict = "Claim has zero linked empirical evidence or observation records."
    elif len(missing_labels) > 0:
        taxonomy = "partially_supported"
        badge_text = f"Evidence incomplete: {', '.join(missing_labels[:2])}"
        coverage_status = "partial"
        summary_verdict = f"Evidence linked but incomplete: {', '.join(missing_labels)}."
    else:
        taxonomy = "well_supported"
        badge_text = "Well-supported"
        coverage_status = "verified"
        summary_verdict = "Verified empirical claim satisfying all sufficiency criteria with active supporting evidence."

    claim_code = getattr(claim, "code", None) or f"CL-{claim.id[:4]}"

    return CoverageResult(
        claim_id=claim.id,
        claim_code=claim_code,
        claim_statement=claim.statement,
        coverage_status=coverage_status,
        taxonomy_status=taxonomy,
        badge_text=badge_text,
        missing_fields=missing_labels,
        checklist=checklist_items,
        summary_verdict=summary_verdict,
    )


async def get_project_coverage(db: AsyncSession, project_id: str) -> List[CoverageResult]:
    """Evaluate coverage across all claims in a project."""
    claims_res = await db.execute(
        select(Claim).where(Claim.project_id == project_id)
    )
    claims = claims_res.scalars().all()
    if not claims:
        return []

    # Batch load edges, contradictions, stale flags
    claim_ids = [c.id for c in claims]
    edges_res = await db.execute(
        select(Edge).where(
            Edge.project_id == project_id,
            Edge.to_id.in_(claim_ids),
            Edge.effective_to.is_(None),
        )
    )
    edges = edges_res.scalars().all()

    contra_res = await db.execute(
        select(Contradiction).where(
            Contradiction.project_id == project_id,
            Contradiction.status == "open",
        )
    )
    contras = contra_res.scalars().all()

    stale_res = await db.execute(
        select(StaleFlag).where(
            StaleFlag.project_id == project_id,
            StaleFlag.status == "active",
        )
    )
    stale_flags = stale_res.scalars().all()

    results: List[CoverageResult] = []
    for c in claims:
        res = await evaluate_claim_coverage(
            db=db,
            claim=c,
            edges=edges,
            contradictions=contras,
            stale_flags=stale_flags,
        )
        results.append(res)
    return results

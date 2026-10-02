import os
import json
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities import (
    Experiment, ExperimentResult, Claim, Edge, DatasetAlias, Document
)

DEFAULT_ALIASES = [
    {"kind": "subject", "canonical": "MobileNetV3-Small", "alias": "Model B"},
    {"kind": "subject", "canonical": "MobileNetV3-Small", "alias": "mobilenet_v3_small"},
    {"kind": "subject", "canonical": "ResNet-18", "alias": "Model A"},
    {"kind": "subject", "canonical": "ResNet-18", "alias": "resnet18"},
    {"kind": "dataset", "canonical": "LeafSet-field", "alias": "real-world images"},
    {"kind": "dataset", "canonical": "LeafSet-field", "alias": "Field Collected Rural MP"},
    {"kind": "dataset", "canonical": "LeafSet-v1", "alias": "PlantVillage Clean v2"},
    {"kind": "metric", "canonical": "f1_score", "alias": "accuracy"},
    {"kind": "metric", "canonical": "f1_score", "alias": "F1"},
    {"kind": "metric", "canonical": "latency_ms", "alias": "latency"},
]

async def ensure_dataset_aliases(db: AsyncSession, project_id: str) -> Dict[str, Dict[str, str]]:
    """
    Loads aliases from database for the project; if none exist, seeds defaults.
    Returns nested dict: {kind: {alias.lower(): canonical}}
    """
    stmt = select(DatasetAlias).where(DatasetAlias.project_id == project_id)
    res = await db.execute(stmt)
    records = res.scalars().all()

    if not records:
        # Seed defaults
        for item in DEFAULT_ALIASES:
            alias_rec = DatasetAlias(
                project_id=project_id,
                kind=item["kind"],
                canonical=item["canonical"],
                alias=item["alias"],
            )
            db.add(alias_rec)
        await db.flush()
        stmt = select(DatasetAlias).where(DatasetAlias.project_id == project_id)
        res = await db.execute(stmt)
        records = res.scalars().all()

    lookup: Dict[str, Dict[str, str]] = {"subject": {}, "dataset": {}, "metric": {}}
    for r in records:
        lookup.setdefault(r.kind, {})[r.alias.lower().strip()] = r.canonical
        lookup.setdefault(r.kind, {})[r.canonical.lower().strip()] = r.canonical

    return lookup

def normalize_key(val: Optional[str], kind: str, lookup: Dict[str, Dict[str, str]]) -> str:
    if not val:
        return ""
    clean = str(val).strip()
    return lookup.get(kind, {}).get(clean.lower(), clean)

async def map_csv_to_results_and_claims(
    db: AsyncSession,
    project_id: str,
    df: pd.DataFrame,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic CSV experiment mapper per Plan §2.6 / TRD Part 35.
    1. Loads / seeds aliases from dataset_aliases table.
    2. Maps each row to Experiment, ExperimentResult, and synthesized Claim.
    3. Links Experiment -> Claim via 'supports' Edge.
    4. NO LLM INVOLVED.
    """
    alias_lookup = await ensure_dataset_aliases(db, project_id)
    
    created_experiments = []
    created_results = []
    created_claims = []
    created_edges = []

    for idx, row in df.iterrows():
        # Read fields with flexible column naming
        exp_code = str(row.get("experiment_code", row.get("code", f"EXP-CSV-{idx+1}"))).strip()
        raw_model = str(row.get("model", row.get("subject", "Unknown Model"))).strip()
        raw_dataset = str(row.get("dataset", "Unknown Dataset")).strip()
        raw_metric = str(row.get("metric", "metric")).strip()
        
        try:
            val = float(row.get("value", 0.0))
        except (ValueError, TypeError):
            val = 0.0

        unit = str(row.get("unit", "")).strip() if pd.notna(row.get("unit")) else ""
        split = str(row.get("split", "test")).strip() if pd.notna(row.get("split")) else "test"
        
        # Condition from lighting or notes
        lighting = str(row.get("lighting", "")).strip() if pd.notna(row.get("lighting")) else ""
        notes = str(row.get("notes", "")).strip() if pd.notna(row.get("notes")) else ""
        condition = lighting or (notes[:100] if notes else None)

        try:
            n_runs = int(row.get("n_runs", 1))
        except (ValueError, TypeError):
            n_runs = 1

        try:
            variance = float(row.get("variance", 0.0)) if pd.notna(row.get("variance")) else None
        except (ValueError, TypeError):
            variance = None

        # Canonical normalization
        canonical_subject = normalize_key(raw_model, "subject", alias_lookup)
        canonical_dataset = normalize_key(raw_dataset, "dataset", alias_lookup)
        canonical_metric = normalize_key(raw_metric, "metric", alias_lookup)

        # 1. Ensure Experiment exists
        exp_stmt = select(Experiment).where(
            Experiment.project_id == project_id,
            Experiment.code == exp_code,
        )
        exp_res = await db.execute(exp_stmt)
        experiment = exp_res.scalars().first()

        if not experiment:
            params = {}
            if lighting:
                params["lighting"] = lighting
            experiment = Experiment(
                project_id=project_id,
                code=exp_code,
                hypothesis=notes or f"Benchmark {raw_model} on {raw_dataset}",
                model=canonical_subject,
                dataset=canonical_dataset,
                parameters=params,
                status="completed",
                origin="system_derived",
                review_status="approved",
            )
            db.add(experiment)
            await db.flush()
            created_experiments.append(experiment)

        # 2. Insert ExperimentResult
        source_text = f"Row {idx+1}: {exp_code} | {raw_model} | {raw_dataset} | {raw_metric}={val}{unit} ({split})"
        if notes:
            source_text += f" | {notes}"

        exp_result = ExperimentResult(
            project_id=project_id,
            experiment_id=experiment.id,
            metric=canonical_metric,
            value=val,
            unit=unit,
            split=split,
            num_runs=n_runs,
            variance=variance,
            source_excerpt=source_text,
            origin="system_derived",
            review_status="approved",
        )
        db.add(exp_result)
        await db.flush()
        created_results.append(exp_result)

        # 3. Synthesize normalized observation Claim for contradiction detection
        stmt_suffix = f" under {condition}" if condition else ""
        claim_statement = f"{canonical_subject} achieves {val}{unit} {canonical_metric} on {canonical_dataset}{stmt_suffix}."

        claim = Claim(
            project_id=project_id,
            statement=claim_statement,
            claim_type="observation",
            subject=canonical_subject,
            metric=canonical_metric,
            direction="equal",
            dataset=canonical_dataset,
            condition=condition,
            value=val,
            coverage_status="supported",
            origin="system_derived",
            review_status="approved",
            document_id=document_id,
            source_excerpt=source_text,
        )
        db.add(claim)
        await db.flush()
        created_claims.append(claim)

        # 4. Link Experiment -> Claim via 'supports' Edge
        edge = Edge(
            project_id=project_id,
            from_type="experiment",
            from_id=experiment.id,
            to_type="claim",
            to_id=claim.id,
            edge_type="supports",
            origin="system_derived",
            review_status="approved",
            rationale_text=f"Directly derived from {exp_code} benchmark results.",
        )
        db.add(edge)
        created_edges.append(edge)

        # If document_id provided, link document -> experiment
        if document_id:
            doc_edge = Edge(
                project_id=project_id,
                from_type="document",
                from_id=document_id,
                to_type="experiment",
                to_id=experiment.id,
                edge_type="describes",
                origin="system_derived",
                review_status="approved",
            )
            db.add(doc_edge)
            created_edges.append(doc_edge)

    await db.flush()
    return {
        "experiments_count": len(created_experiments),
        "results_count": len(created_results),
        "claims_count": len(created_claims),
        "edges_count": len(created_edges),
    }

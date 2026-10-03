import math
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.core.auth import UserScope
from app.models.entities import (
    Chunk, Document, Decision, Experiment, ExperimentResult, Task, Claim, Edge
)
from app.rag.permissions import get_visibility_filter
from app.rag.intent import QueryIntent
from app.ai.providers.factory import get_embedding_provider

class RetrievedContextItem(BaseModel):
    id: str
    entity_type: str  # document_chunk, decision, experiment, task, claim
    code_or_title: str
    text_content: str
    origin: str = "human_authored"  # human_authored, system_derived, ai_inferred
    source_date: Optional[str] = None
    notion_url: Optional[str] = None
    score: float = 1.0
    visibility: str = "project"
    entity_record: Optional[Dict[str, Any]] = None

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)

async def perform_rag_retrieval(
    db: AsyncSession,
    project_id: str,
    query: str,
    scope: UserScope,
    intent: QueryIntent,
    top_k: int = 8,
    as_of: Optional[str] = None,
) -> List[RetrievedContextItem]:
    """
    Plan §4.1 & §4.3: Permission-filtered hybrid retrieval.
    Applies user_scopes() filter BEFORE ranking.
    Scans document chunks (keyword + semantic exact scan) and structured entities.
    """
    clean_q = query.strip()
    items: List[RetrievedContextItem] = []
    
    # ---------------- 1. Chunks Hybrid Search (Permission Filter First) ----------------
    doc_filter = get_visibility_filter(scope, Document)
    chunk_stmt = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            and_(
                Chunk.project_id == project_id,
                doc_filter,
            )
        )
    )
    chunk_res = await db.execute(chunk_stmt)
    chunk_candidates = chunk_res.all()

    if chunk_candidates:
        embed_provider = get_embedding_provider()
        query_vector = await embed_provider.embed_text(clean_q)
        query_terms = [t.lower() for t in clean_q.split() if len(t) > 1]

        scored_chunks = []
        for chunk, doc in chunk_candidates:
            c_text_lower = chunk.text.lower()
            title_lower = (doc.title or "").lower()

            # Keyword match
            matched_terms = sum(1 for term in query_terms if term in c_text_lower or term in title_lower)
            kw_score = matched_terms / max(1, len(query_terms)) if query_terms else 0.0

            # Semantic match
            sem_score = 0.0
            if chunk.embedding and isinstance(chunk.embedding, list):
                sim = cosine_similarity(query_vector, chunk.embedding)
                sem_score = max(0.0, (sim + 1.0) / 2.0)

            # Boost exact code mentions
            code_boost = 0.0
            for code in intent.entity_codes:
                if code.lower() in c_text_lower or code.lower() in title_lower:
                    code_boost += 0.25

            score = 0.4 * kw_score + 0.6 * sem_score + code_boost
            scored_chunks.append((score, chunk, doc))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        for score, chunk, doc in scored_chunks[:top_k]:
            if score > 0.05:
                doc_date_str = doc.doc_date.strftime("%Y-%m-%d") if doc.doc_date else None
                items.append(
                    RetrievedContextItem(
                        id=chunk.id,
                        entity_type="document_chunk",
                        code_or_title=f"{doc.title} [{chunk.heading_path or 'Section'}]",
                        text_content=chunk.text,
                        origin=doc.origin or "human_authored",
                        source_date=doc_date_str,
                        notion_url=doc.notion_url,
                        score=score,
                        visibility=doc.visibility,
                        entity_record={"document_id": doc.id, "char_start": chunk.char_start, "char_end": chunk.char_end},
                    )
                )

    # ---------------- 2. Structured Decisions (Permission Filter First) ----------------
    dec_filter = get_visibility_filter(scope, Decision)
    dec_stmt = select(Decision).where(and_(Decision.project_id == project_id, dec_filter))
    dec_res = await db.execute(dec_stmt)
    all_decisions = dec_res.scalars().all()

    for d in all_decisions:
        # Match if code mentioned, model alias mentioned, or high lexical overlap
        is_targeted = d.code in intent.entity_codes
        matches_alias = any(m.lower() in d.statement.lower() for m in intent.model_aliases)
        text_match = clean_q.lower() in d.statement.lower() or (d.rationale and clean_q.lower() in d.rationale.lower())
        
        if is_targeted or matches_alias or text_match or intent.intent_type == "decision":
            dec_date_str = d.decided_on.strftime("%Y-%m-%d") if d.decided_on else None
            rationale_part = f"\nRationale: {d.rationale}" if d.rationale else ""
            alts_part = f"\nAlternatives considered: {d.alternatives}" if d.alternatives else ""
            score = 1.0 if is_targeted else 0.8
            items.append(
                RetrievedContextItem(
                    id=d.id,
                    entity_type="decision",
                    code_or_title=f"Decision {d.code}",
                    text_content=f"{d.statement}{rationale_part}{alts_part}",
                    origin=d.origin or "human_authored",
                    source_date=dec_date_str,
                    notion_url=d.notion_url,
                    score=score,
                    visibility=d.visibility,
                    entity_record={"code": d.code, "status": d.status, "version": d.version},
                )
            )

    # ---------------- 3. Structured Experiments (Permission Filter First) ----------------
    exp_filter = get_visibility_filter(scope, Experiment)
    exp_stmt = select(Experiment).where(and_(Experiment.project_id == project_id, exp_filter))
    exp_res = await db.execute(exp_stmt)
    all_experiments = exp_res.scalars().all()

    for e in all_experiments:
        is_targeted = e.code in intent.entity_codes
        model_match = any(m.lower() in (e.model or "").lower() for m in intent.model_aliases)
        
        if is_targeted or model_match or intent.intent_type == "experiment":
            # Fetch results for this experiment
            r_stmt = select(ExperimentResult).where(ExperimentResult.experiment_id == e.id)
            r_res = await db.execute(r_stmt)
            results = r_res.scalars().all()
            res_str = ", ".join([f"{r.metric}: {r.value} {r.unit or ''}" for r in results])
            exp_content = f"Experiment {e.code} ({e.model or ''}) on dataset {e.dataset or 'default'}. Hypothesis: {e.hypothesis or 'N/A'}. Results: [{res_str}]"
            score = 1.0 if is_targeted else 0.75
            items.append(
                RetrievedContextItem(
                    id=e.id,
                    entity_type="experiment",
                    code_or_title=f"Experiment {e.code}",
                    text_content=exp_content,
                    origin=e.origin or "system_derived",
                    source_date=e.run_date.strftime("%Y-%m-%d") if e.run_date else None,
                    notion_url=e.notion_url,
                    score=score,
                    visibility=e.visibility,
                    entity_record={"code": e.code, "model": e.model},
                )
            )

    # ---------------- 4. Structured Tasks (Permission Filter First) ----------------
    task_filter = get_visibility_filter(scope, Task)
    task_stmt = select(Task).where(and_(Task.project_id == project_id, task_filter))
    task_res = await db.execute(task_stmt)
    all_tasks = task_res.scalars().all()

    for t in all_tasks:
        is_targeted = t.code in intent.entity_codes
        person_match = any(p.lower() in (t.owner or "").lower() for p in intent.people_mentions)
        
        if is_targeted or person_match or intent.intent_type == "task":
            due_str = t.due_date.strftime("%Y-%m-%d") if t.due_date else "No due date"
            task_content = f"Task {t.code}: {t.title}. Owner: {t.owner or 'Unassigned'}. Due: {due_str}. Status: {t.status}. Priority: {t.priority}."
            score = 1.0 if is_targeted else 0.7
            items.append(
                RetrievedContextItem(
                    id=t.id,
                    entity_type="task",
                    code_or_title=f"Task {t.code}",
                    text_content=task_content,
                    origin=t.origin or "human_authored",
                    source_date=due_str,
                    notion_url=t.notion_url,
                    score=score,
                    visibility=t.visibility,
                    entity_record={"code": t.code, "owner": t.owner, "status": t.status},
                )
            )

    # ---------------- 5. Structured Claims (Permission Filter First) ----------------
    claim_filter = get_visibility_filter(scope, Claim)
    claim_stmt = select(Claim).where(and_(Claim.project_id == project_id, claim_filter))
    claim_res = await db.execute(claim_stmt)
    all_claims = claim_res.scalars().all()

    for c in all_claims:
        is_relevant = any(w in c.statement.lower() for w in intent.keywords) or any(m.lower() in (c.subject or "").lower() for m in intent.model_aliases)
        if is_relevant:
            items.append(
                RetrievedContextItem(
                    id=c.id,
                    entity_type="claim",
                    code_or_title=f"Claim ({c.subject or 'General'})",
                    text_content=c.statement,
                    origin=c.origin or "human_authored",
                    score=0.7,
                    visibility=c.visibility,
                    entity_record={"subject": c.subject, "metric": c.metric, "direction": c.direction},
                )
            )

    # Sort all retrieved items by score descending and deduplicate by id
    seen_ids = set()
    deduped_items = []
    items.sort(key=lambda x: x.score, reverse=True)
    for it in items:
        if it.id not in seen_ids:
            seen_ids.add(it.id)
            deduped_items.append(it)

    return deduped_items[:top_k]

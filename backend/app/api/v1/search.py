import math
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.entities import Chunk, Document
from app.ai.providers.factory import get_embedding_provider

router = APIRouter(tags=["Search"])

class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    doc_type: Optional[str] = None
    heading_path: Optional[str] = None
    char_start: int
    char_end: int
    text: str
    score: float
    match_type: str  # keyword, semantic, hybrid

class SearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResultItem]

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)

@router.get("/search", response_model=SearchResponse)
async def hybrid_search(
    project_id: str = Query(..., description="Project ID"),
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    doc_type: Optional[str] = Query(None, description="Optional document type filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    Task 2.8: Hybrid search (keyword + semantic exact scan) filtered by project_id and doc_type.
    """
    clean_q = q.strip()
    if not clean_q:
        return SearchResponse(query=q, total=0, results=[])

    # 1. Fetch candidate chunks with their document metadata
    stmt = (
        select(Chunk, Document.title, Document.doc_type)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.project_id == project_id)
    )
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)

    res = await db.execute(stmt)
    candidates = res.all()

    if not candidates:
        return SearchResponse(query=q, total=0, results=[])

    # 2. Compute query embedding for semantic search
    embed_provider = get_embedding_provider()
    query_vector = await embed_provider.embed_text(clean_q)

    # 3. Score and rank candidates
    scored_items = []
    query_terms = [t.lower() for t in clean_q.split() if len(t) > 1]

    for chunk, doc_title, d_type in candidates:
        chunk_text_lower = chunk.text.lower()
        title_lower = (doc_title or "").lower()

        # Keyword matching score
        matched_terms = sum(1 for term in query_terms if term in chunk_text_lower or term in title_lower)
        keyword_score = matched_terms / max(1, len(query_terms)) if query_terms else 0.0

        # Semantic cosine similarity
        semantic_score = 0.0
        if chunk.embedding and isinstance(chunk.embedding, list):
            sim = cosine_similarity(query_vector, chunk.embedding)
            # Map [-1, 1] to [0, 1]
            semantic_score = max(0.0, (sim + 1.0) / 2.0)

        # Determine match type and hybrid score
        if keyword_score > 0.0 and semantic_score > 0.4:
            score = 0.4 * keyword_score + 0.6 * semantic_score
            match_type = "hybrid"
        elif keyword_score > 0.0:
            score = 0.8 * keyword_score + 0.2 * semantic_score
            match_type = "keyword"
        else:
            score = semantic_score
            match_type = "semantic"

        # Boost exact phrase match
        if clean_q.lower() in chunk_text_lower or clean_q.lower() in title_lower:
            score = min(1.0, score + 0.2)
            if match_type == "semantic":
                match_type = "hybrid"

        scored_items.append((score, match_type, chunk, doc_title, d_type))

    # Sort descending by score
    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = scored_items[:limit]

    results = [
        SearchResultItem(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=doc_title,
            doc_type=d_type,
            heading_path=chunk.heading_path,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            text=chunk.text,
            score=round(score, 4),
            match_type=match_type,
        )
        for score, match_type, chunk, doc_title, d_type in top_items
    ]

    return SearchResponse(
        query=q,
        total=len(results),
        results=results,
    )

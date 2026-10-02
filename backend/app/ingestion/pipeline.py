import os
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.entities import Document, Chunk
from app.ingestion.parsers import parse_file
from app.ingestion.classifier import classify_document_type
from app.ingestion.chunker import create_structure_aware_chunks
from app.ingestion.csv_mapper import map_csv_to_results_and_claims
from app.ai.providers.factory import get_embedding_provider
from workers.runner import register_handler, emit_job_event
from app.core.logging import logger

async def ingest_document(
    db: AsyncSession,
    document_id: str,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the ingestion pipeline for a document:
    1. Parsing -> Extract text and blocks with character offsets.
    2. Classifying -> Determine document category (heuristic / LLM).
    3. Chunking -> Structure-aware chunks preserving full_text[start:end] == chunk_text.
    4. Embedding -> Compute 384-d dense vectors.
    5. CSV Mapping -> If CSV, deterministically map to experiments and claims without LLM.
    6. State machine progression with SSE job_events.
    """
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    document = res.scalars().first()

    if not document:
        raise ValueError(f"Document {document_id} not found")

    try:
        # Step 1: Parsing
        document.pipeline_status = "parsing"
        await db.commit()
        if job_id:
            await emit_job_event(db, job_id, "parsing", f"Parsing document: {document.title}")

        file_path = document.file_uri
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found at: {file_path}")

        full_text, blocks, metadata = parse_file(file_path)
        document.content_text = full_text

        # Step 2: Classifying
        document.pipeline_status = "classifying"
        await db.commit()
        if job_id:
            await emit_job_event(db, job_id, "classifying", f"Classifying document type")

        override = document.doc_type if document.doc_type and document.doc_type != "note" else None
        classified_type = await classify_document_type(document.title, full_text, user_override=override)
        document.doc_type = classified_type

        # Step 3: Chunking
        document.pipeline_status = "chunking"
        await db.commit()
        if job_id:
            await emit_job_event(db, job_id, "chunking", f"Generating structure-aware chunks")

        chunks_data = create_structure_aware_chunks(full_text, blocks)
        
        # Fallback if no blocks or text was short
        if not chunks_data and full_text.strip():
            chunks_data = [{
                "text": full_text,
                "heading_path": "General",
                "char_start": 0,
                "char_end": len(full_text),
            }]

        # Step 4: Embedding
        if job_id:
            await emit_job_event(db, job_id, "embedding", f"Embedding {len(chunks_data)} chunks")

        embed_provider = get_embedding_provider()
        chunk_texts = [c["text"] for c in chunks_data]
        vectors = await embed_provider.embed_batch(chunk_texts) if chunk_texts else []

        # Store chunks
        for idx, c in enumerate(chunks_data):
            vec = vectors[idx] if idx < len(vectors) else None
            chunk_rec = Chunk(
                project_id=document.project_id,
                document_id=document.id,
                heading_path=c.get("heading_path", "General"),
                char_start=c["char_start"],
                char_end=c["char_end"],
                text=c["text"],
                embedding=vec,
            )
            db.add(chunk_rec)
        
        await db.flush()

        # Step 5: Deterministic CSV Mapping if applicable
        csv_stats = None
        if "dataframe" in metadata and metadata["dataframe"] is not None:
            if job_id:
                await emit_job_event(db, job_id, "csv_mapping", "Mapping experiment results and synthesizing claims")
            csv_stats = await map_csv_to_results_and_claims(
                db=db,
                project_id=document.project_id,
                df=metadata["dataframe"],
                document_id=document.id,
            )

        # Step 6: Completion
        if document.doc_type == "meeting_note":
            from workers.runner import enqueue_job
            await enqueue_job(
                db=db,
                job_type="extraction",
                payload={"document_id": document.id},
                project_id=document.project_id
            )
            document.pipeline_status = "chunked"
        else:
            document.pipeline_status = "completed"
            
        await db.commit()
        
        if job_id:
            await emit_job_event(
                db, job_id, "completed",
                f"Successfully ingested {document.title} ({len(chunks_data)} chunks, {document.doc_type})"
            )

        logger.info(
            "document_ingested",
            document_id=document.id,
            project_id=document.project_id,
            chunks_count=len(chunks_data),
            doc_type=document.doc_type,
            csv_stats=csv_stats,
        )

        return {
            "document_id": document.id,
            "title": document.title,
            "doc_type": document.doc_type,
            "chunks_count": len(chunks_data),
            "csv_stats": csv_stats,
            "status": "completed",
        }

    except Exception as e:
        document.pipeline_status = "failed"
        await db.commit()
        if job_id:
            await emit_job_event(db, job_id, "failed", f"Ingestion error: {str(e)}")
        logger.error("document_ingest_failed", document_id=document_id, error=str(e))
        raise

@register_handler("document_ingest")
async def handle_document_ingest_job(db: AsyncSession, job: Any):
    """Job runner worker handler for 'document_ingest'."""
    doc_id = job.payload.get("document_id")
    if not doc_id:
        raise ValueError("Missing 'document_id' in job payload")
    
    return await ingest_document(db, doc_id, job_id=job.id)

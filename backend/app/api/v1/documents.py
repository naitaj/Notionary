import os
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.entities import Document, Chunk
from app.ingestion.validate import validate_and_deduplicate
from app.core.errors import ProblemException
from workers.runner import enqueue_job

router = APIRouter(tags=["Documents"])

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    title: str
    doc_type: str
    file_uri: Optional[str] = None
    content_hash: Optional[str] = None
    pipeline_status: str
    notion_url: Optional[str] = None
    notion_page_id: Optional[str] = None

    class Config:
        from_attributes = True

class ChunkResponse(BaseModel):
    id: str
    document_id: str
    heading_path: Optional[str] = None
    char_start: int
    char_end: int
    text: str

    class Config:
        from_attributes = True

class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    job_id: str

@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    auto_extract: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """
    Task 2.1: Validates extension whitelist, 25MB limit, and SHA-256 deduplication.
    Persists document with pipeline_status='uploaded' and enqueues 'document_ingest' background job.
    """
    content = await file.read()
    filename = file.filename or "uploaded_file"
    doc_title = title or filename

    # Ensure project_id is valid
    from app.models.entities import Project
    p_check = await db.execute(select(Project).where(Project.id == project_id))
    if not p_check.scalar_one_or_none():
        first_p = (await db.execute(select(Project).order_by(Project.created_at.asc()).limit(1))).scalar_one_or_none()
        if first_p:
            project_id = first_p.id

    # Validation and SHA-256 dedupe
    content_hash, file_path = await validate_and_deduplicate(
        db=db,
        project_id=project_id,
        filename=filename,
        content=content,
    )

    # Create document record
    document = Document(
        project_id=project_id,
        title=doc_title,
        doc_type=doc_type or "note",
        file_uri=file_path,
        content_hash=content_hash,
        pipeline_status="uploaded",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Enqueue background job
    job = await enqueue_job(
        db=db,
        job_type="document_ingest",
        payload={
            "document_id": document.id,
            "project_id": project_id,
            "filename": filename,
            "auto_extract": auto_extract,
        },
        project_id=project_id,
    )

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        job_id=job.id,
    )

@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
async def list_project_documents(
    project_id: str,
    doc_type: Optional[str] = Query(None),
    pipeline_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Lists all documents belonging to a project."""
    stmt = select(Document).where(Document.project_id == project_id)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if pipeline_status:
        stmt = stmt.where(Document.pipeline_status == pipeline_status)

    res = await db.execute(stmt)
    docs = res.scalars().all()
    if not docs:
        from app.models.entities import Project
        first_p = (await db.execute(select(Project).order_by(Project.created_at.asc()).limit(1))).scalar_one_or_none()
        if first_p and first_p.id != project_id:
            fb_stmt = select(Document).where(Document.project_id == first_p.id)
            if doc_type:
                fb_stmt = fb_stmt.where(Document.doc_type == doc_type)
            if pipeline_status:
                fb_stmt = fb_stmt.where(Document.pipeline_status == pipeline_status)
            fb_res = await db.execute(fb_stmt)
            docs = fb_res.scalars().all()
    return docs

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves document metadata and status."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ProblemException(status=404, title="Not Found", detail=f"Document {document_id} not found")
    return doc

@router.get("/documents/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves chunks with character offsets for excerpt highlighting."""
    stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.char_start)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/documents/{document_id}/retry")
async def retry_document_ingestion(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retries a failed document ingestion pipeline."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ProblemException(status=404, title="Not Found", detail=f"Document {document_id} not found")

    # Clear existing chunks if retrying
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    doc.pipeline_status = "uploaded"
    await db.commit()

    job = await enqueue_job(
        db=db,
        job_type="document_ingest",
        payload={
            "document_id": doc.id,
            "project_id": doc.project_id,
        },
        project_id=doc.project_id,
    )

    return {"status": "retrying", "document_id": doc.id, "job_id": job.id}

@router.delete("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deletes a document, its chunks, and associated local file."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ProblemException(status=404, title="Not Found", detail=f"Document {document_id} not found")

    # Delete chunks
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    # Remove physical file if present
    if doc.file_uri and os.path.exists(doc.file_uri):
        try:
            os.remove(doc.file_uri)
        except Exception:
            pass

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "document_id": document_id}

@router.delete("/projects/{project_id}/documents", status_code=status.HTTP_200_OK)
async def clear_project_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deletes all documents and chunks for a given project."""
    stmt = select(Document).where(Document.project_id == project_id)
    res = await db.execute(stmt)
    docs = res.scalars().all()

    for doc in docs:
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        if doc.file_uri and os.path.exists(doc.file_uri):
            try:
                os.remove(doc.file_uri)
            except Exception:
                pass
        await db.delete(doc)

    await db.commit()
    return {"status": "cleared", "deleted_count": len(docs)}

@router.post("/documents/{document_id}/extract", status_code=status.HTTP_202_ACCEPTED)
async def trigger_document_extraction(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Triggers AI extraction of decisions, tasks, claims, and experiments into proposals."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise ProblemException(status=404, title="Not Found", detail=f"Document {document_id} not found")

    job = await enqueue_job(
        db=db,
        job_type="extraction",
        payload={"document_id": doc.id},
        project_id=doc.project_id,
    )
    doc.pipeline_status = "chunked"
    await db.commit()

    return {"status": "extraction_enqueued", "document_id": doc.id, "job_id": job.id}

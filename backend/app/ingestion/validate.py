import hashlib
import os
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import Document
from app.core.errors import ProblemException

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".txt", ".csv"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB

def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

async def validate_and_deduplicate(
    db: AsyncSession,
    project_id: str,
    filename: str,
    content: bytes,
    storage_dir: str = "storage/documents",
) -> Tuple[str, str]:
    """
    Validates file extension, size limit, and performs SHA-256 deduplication.
    Returns (content_hash, file_uri).
    """
    # 1. Check extension
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ProblemException(
            status=400,
            title="Unsupported File Type",
            detail=f"File extension '{ext}' is not supported. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Check size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ProblemException(
            status=400,
            title="File Too Large",
            detail=f"File exceeds maximum allowed size of 25MB (got {len(content) / (1024*1024):.1f}MB).",
        )

    # 3. Compute hash
    content_hash = compute_sha256(content)

    # 4. Check for duplicate upload in project
    stmt = select(Document).where(
        Document.project_id == project_id,
        Document.content_hash == content_hash,
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        raise ProblemException(
            status=409,
            title="Duplicate Document",
            detail=f"This document was already uploaded to this project as '{existing.title}' (ID: {existing.id}).",
        )

    # 5. Persist file to local storage
    os.makedirs(storage_dir, exist_ok=True)
    saved_filename = f"{content_hash}{ext}"
    file_path = os.path.join(storage_dir, saved_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    return content_hash, file_path

import os
import io
import pytest
import pandas as pd
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.database import engine, Base, AsyncSessionLocal
from app.models.entities import Project, Document, Chunk, Experiment, ExperimentResult, Claim, Edge
from app.ingestion.parsers import parse_file
from app.ingestion.parsers.markdown import parse_markdown
from app.ingestion.parsers.text import parse_plain_text
from app.ingestion.parsers.csv_parser import parse_csv_file
from app.ingestion.chunker import create_structure_aware_chunks
from app.ingestion.csv_mapper import map_csv_to_results_and_claims
from app.ingestion.pipeline import ingest_document
from workers.runner import process_next_job

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_character_offset_roundtrip_invariant():
    """
    Mandatory Plan §2 Invariant:
    full_text[chunk['char_start']:chunk['char_end']] == chunk['text'] for all chunks.
    """
    # 1. Test Markdown
    doc05_path = "fixtures/leafguard/DOC-05.md"
    assert os.path.exists(doc05_path), f"Fixture missing: {doc05_path}"
    full_text_md, blocks_md, _ = parse_file(doc05_path)
    chunks_md = create_structure_aware_chunks(full_text_md, blocks_md)
    assert len(chunks_md) > 0

    for idx, c in enumerate(chunks_md):
        extracted_slice = full_text_md[c["char_start"]:c["char_end"]]
        assert extracted_slice == c["text"], f"Offset mismatch in Markdown chunk {idx}: '{extracted_slice}' != '{c['text']}'"

    # 2. Test Plain Text
    log01_path = "fixtures/leafguard/LOG-01.txt"
    assert os.path.exists(log01_path), f"Fixture missing: {log01_path}"
    full_text_txt, blocks_txt, _ = parse_file(log01_path)
    chunks_txt = create_structure_aware_chunks(full_text_txt, blocks_txt)
    assert len(chunks_txt) > 0

    for idx, c in enumerate(chunks_txt):
        extracted_slice = full_text_txt[c["char_start"]:c["char_end"]]
        assert extracted_slice == c["text"], f"Offset mismatch in Text chunk {idx}: '{extracted_slice}' != '{c['text']}'"

    # 3. Test CSV
    csv_path = "fixtures/leafguard/EXP-09.csv"
    assert os.path.exists(csv_path), f"Fixture missing: {csv_path}"
    full_text_csv, blocks_csv, _ = parse_file(csv_path)
    chunks_csv = create_structure_aware_chunks(full_text_csv, blocks_csv)
    assert len(chunks_csv) > 0

    for idx, c in enumerate(chunks_csv):
        extracted_slice = full_text_csv[c["char_start"]:c["char_end"]]
        assert extracted_slice == c["text"], f"Offset mismatch in CSV chunk {idx}: '{extracted_slice}' != '{c['text']}'"

@pytest.mark.asyncio
async def test_duplicate_upload_rejection_and_validation():
    """
    Task 2.1: Validates whitelist, 25MB limit, and returns 409 Conflict on identical content_hash.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a project
        proj_resp = await client.post("/api/v1/projects", json={"name": "Ingestion Test Project"})
        assert proj_resp.status_code == 200
        proj_id = proj_resp.json()["id"]

        # 2. Test invalid extension rejection
        fake_exe = io.BytesIO(b"MZ\x90\x00malicious binary content")
        bad_ext_resp = await client.post(
            f"/api/v1/projects/{proj_id}/documents",
            files={"file": ("exploit.exe", fake_exe, "application/octet-stream")},
        )
        assert bad_ext_resp.status_code == 400
        assert "Unsupported File Type" in bad_ext_resp.json()["title"]

        # 3. First upload of valid Markdown
        doc_content = b"# Architecture Overview\nMobileNetV3 deployed to edge device."
        file_obj1 = io.BytesIO(doc_content)
        upload_resp1 = await client.post(
            f"/api/v1/projects/{proj_id}/documents",
            files={"file": ("arch.md", file_obj1, "text/markdown")},
            data={"title": "Architecture Overview"},
        )
        assert upload_resp1.status_code == 201
        data1 = upload_resp1.json()
        assert data1["document"]["pipeline_status"] == "uploaded"
        assert data1["job_id"] is not None

        # 4. Duplicate upload of identical content -> Expect 409 Conflict
        file_obj2 = io.BytesIO(doc_content)
        upload_resp2 = await client.post(
            f"/api/v1/projects/{proj_id}/documents",
            files={"file": ("arch_duplicate.md", file_obj2, "text/markdown")},
            data={"title": "Duplicate Arch"},
        )
        assert upload_resp2.status_code == 409
        assert "Duplicate Document" in upload_resp2.json()["title"]

@pytest.mark.asyncio
async def test_deterministic_csv_mapper_leafguard():
    """
    Task 2.6: Deterministic CSV mapper maps EXP-09.csv to experiment_results and normalized claims
    with alias normalization and no LLM hallucinations.
    """
    async with AsyncSessionLocal() as session:
        # Create test project
        project = Project(name="CSV Mapping Test Project")
        session.add(project)
        await session.commit()
        await session.refresh(project)

        csv_path = "fixtures/leafguard/EXP-09.csv"
        df = pd.read_csv(csv_path)

        stats = await map_csv_to_results_and_claims(
            db=session,
            project_id=project.id,
            df=df,
            document_id=None,
        )
        await session.commit()

        assert stats["results_count"] == 4  # 4 rows in EXP-09.csv
        assert stats["claims_count"] == 4

        # Verify results in database
        stmt = select(ExperimentResult).where(ExperimentResult.project_id == project.id)
        res = await session.execute(stmt)
        results = res.scalars().all()
        assert len(results) == 4

        # Check alias normalization on Claim
        # 'Field Collected Rural MP' should normalize to 'LeafSet-field'
        claim_stmt = select(Claim).where(Claim.project_id == project.id)
        claim_res = await session.execute(claim_stmt)
        claims = claim_res.scalars().all()
        assert len(claims) == 4

        field_claims = [c for c in claims if c.dataset == "LeafSet-field"]
        assert len(field_claims) == 2  # rows 1 and 2 of EXP-09.csv
        assert any(c.metric == "f1_score" and c.value == 78.5 for c in field_claims)
        assert any(c.metric == "latency_ms" and c.value == 14.8 for c in field_claims)

        # Check edge created between experiment and claim
        edge_stmt = select(Edge).where(Edge.project_id == project.id, Edge.edge_type == "supports")
        edge_res = await session.execute(edge_stmt)
        edges = edge_res.scalars().all()
        assert len(edges) >= 4

@pytest.mark.asyncio
async def test_end_to_end_document_ingest_and_search():
    """
    Tasks 2.5, 2.7, 2.8: Upload document -> worker runs document_ingest -> chunks embedded -> hybrid search queries return results.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project
        proj_resp = await client.post("/api/v1/projects", json={"name": "Pipeline E2E Project"})
        proj_id = proj_resp.json()["id"]

        # Upload DOC-05.md
        with open("fixtures/leafguard/DOC-05.md", "rb") as f:
            md_bytes = f.read()

        up_resp = await client.post(
            f"/api/v1/projects/{proj_id}/documents",
            files={"file": ("DOC-05.md", io.BytesIO(md_bytes), "text/markdown")},
            data={"title": "DOC-05 Edge System Spec"},
        )
        assert up_resp.status_code == 201
        doc_id = up_resp.json()["document"]["id"]
        job_id = up_resp.json()["job_id"]

        # Execute background job via runner
        async with AsyncSessionLocal() as session:
            job_ran = await process_next_job(db=session, job_id=job_id)
            assert job_ran is True

        # Check document status is completed
        doc_resp = await client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        assert doc_resp.json()["pipeline_status"] == "completed"

        # Check chunks endpoint
        chunks_resp = await client.get(f"/api/v1/documents/{doc_id}/chunks")
        assert chunks_resp.status_code == 200
        chunks = chunks_resp.json()
        assert len(chunks) > 0
        assert all("char_start" in c and "char_end" in c and "text" in c for c in chunks)

        # Search endpoint: Keyword query
        search_kw = await client.get(f"/api/v1/search?project_id={proj_id}&q=MobileNetV3")
        assert search_kw.status_code == 200
        kw_data = search_kw.json()
        assert kw_data["total"] > 0
        assert any("MobileNetV3" in item["text"] for item in kw_data["results"])

        # Search endpoint: Semantic query
        search_sem = await client.get(f"/api/v1/search?project_id={proj_id}&q=edge+inference+budget+and+latency")
        assert search_sem.status_code == 200
        sem_data = search_sem.json()
        assert sem_data["total"] > 0
        assert sem_data["results"][0]["score"] > 0.0

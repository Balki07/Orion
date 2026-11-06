"""Integration tests covering PDF upload, ingestion, Q&A, citations, paper comparison, notes, and deletion."""

import io
import pytest
from app.services.ingestion.pipeline import get_ingestion_pipeline


@pytest.mark.asyncio
async def test_full_document_lifecycle_and_qa(client, sample_pdf_bytes):
    """Test full flow: upload -> complete ingestion -> question -> citation -> note -> delete."""
    headers_user_a = {"X-User-Id": "user_researcher_a"}

    # 1. Upload Document
    files = {"file": ("attention_is_all_you_need.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    resp = await client.post("/api/v1/documents", files=files, headers=headers_user_a)
    assert resp.status_code == 201
    doc_data = resp.json()
    doc_id = doc_data["id"]
    assert doc_data["filename"] == "attention_is_all_you_need.pdf"

    # 2. Process ingestion via pipeline
    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # 3. Check document status
    status_resp = await client.get(f"/api/v1/documents/{doc_id}/status", headers=headers_user_a)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"
    assert status_resp.json()["chunk_count"] > 0
    assert status_resp.json()["page_count"] == 2

    # 4. Check page inspection endpoint
    page_resp = await client.get(f"/api/v1/documents/{doc_id}/pages/2", headers=headers_user_a)
    assert page_resp.status_code == 200
    assert "Scaled Dot-Product Attention" in page_resp.json()["text"]

    # 4b. Check raw PDF file streaming endpoint
    file_resp = await client.get(f"/api/v1/documents/{doc_id}/file", headers=headers_user_a)
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "application/pdf"
    assert len(file_resp.content) > 0

    # 4c. Check crisp page PNG rendering endpoint
    render_resp = await client.get(f"/api/v1/documents/{doc_id}/pages/2/render", headers=headers_user_a)
    assert render_resp.status_code == 200
    assert render_resp.headers["content-type"] == "image/png"
    assert len(render_resp.content) > 0

    # 4d. Out-of-bounds page rendering yields validation error
    invalid_render = await client.get(f"/api/v1/documents/{doc_id}/pages/99/render", headers=headers_user_a)
    assert invalid_render.status_code in (400, 422)

    # 5. Ask answerable question
    ask_payload = {
        "question": "What is the formula for Scaled Dot-Product Attention and what BLEU score was achieved?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    ask_resp = await client.post("/api/v1/research/ask", json=ask_payload, headers=headers_user_a)
    assert ask_resp.status_code == 200
    answer_data = ask_resp.json()

    assert not answer_data["insufficient_evidence"]
    assert len(answer_data["citations"]) > 0

    first_cite = answer_data["citations"][0]
    assert first_cite["document_id"] == doc_id
    assert first_cite["filename"] == "attention_is_all_you_need.pdf"
    assert len(first_cite["page_numbers"]) >= 1

    # 6. Ask unanswerable question (abstention protocol)
    unanswerable_payload = {
        "question": "What is the quantum computing simulation benchmark reported for the Transformer?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    abstain_resp = await client.post("/api/v1/research/ask", json=unanswerable_payload, headers=headers_user_a)
    assert abstain_resp.status_code == 200
    abstain_data = abstain_resp.json()
    assert abstain_data["insufficient_evidence"] is True

    # 7. Create Note and Export
    note_payload = {
        "title": "Transformer Attention Mechanics",
        "content": answer_data["answer"],
        "source_citations": answer_data["citations"],
    }
    note_resp = await client.post("/api/v1/notes", json=note_payload, headers=headers_user_a)
    assert note_resp.status_code == 201
    note_id = note_resp.json()["id"]

    export_resp = await client.get(f"/api/v1/notes/{note_id}/export", headers=headers_user_a)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "# Transformer Attention Mechanics" in export_data["markdown_content"]
    assert "attention_is_all_you_need.pdf" in export_data["markdown_content"]

    # 8. Cross-User Isolation check: User B cannot access User A's document
    headers_user_b = {"X-User-Id": "user_researcher_b"}
    forbidden_resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_user_b)
    assert forbidden_resp.status_code == 403

    # 9. Delete Document
    del_resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_user_a)
    assert del_resp.status_code == 204

    # Verify document is gone
    gone_resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_user_a)
    assert gone_resp.status_code == 404


@pytest.mark.asyncio
async def test_batch_upload_multiple_valid_pdfs(client, sample_pdf_bytes):
    """Test batch uploading multiple valid research PDFs simultaneously."""
    headers = {"X-User-Id": "user_batch_tester"}

    files = [
        ("files", ("paper_1.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
        ("files", ("paper_2.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
    ]
    resp = await client.post("/api/v1/documents/batch", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["total"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0
    assert len(data["items"]) == 2

    # Verify both documents received distinct IDs
    doc1 = data["items"][0]["document"]
    doc2 = data["items"][1]["document"]
    assert doc1 is not None and doc2 is not None
    assert doc1["id"] != doc2["id"]
    assert doc1["owner_id"] == "user_batch_tester"


@pytest.mark.asyncio
async def test_batch_upload_partial_failure(client, sample_pdf_bytes):
    """Test batch uploading with mixed valid, non-PDF, and corrupt files."""
    headers = {"X-User-Id": "user_partial_tester"}

    corrupt_pdf_bytes = b"Not a real PDF without header"
    files = [
        ("files", ("valid.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
        ("files", ("invalid.txt", io.BytesIO(b"Hello world"), "text/plain")),
        ("files", ("corrupted.pdf", io.BytesIO(corrupt_pdf_bytes), "application/pdf")),
    ]
    resp = await client.post("/api/v1/documents/batch", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["total"] == 3
    assert data["successful_count"] == 1
    assert data["failed_count"] == 2

    # First item succeeded
    assert data["items"][0]["status"] == "queued"
    assert data["items"][0]["document"]["filename"] == "valid.pdf"

    # Second item rejected (non-PDF)
    assert data["items"][1]["status"] == "rejected"
    assert "Only PDF documents" in data["items"][1]["error"]

    # Third item rejected (bad magic bytes)
    assert data["items"][2]["status"] == "rejected"
    assert "PDF header signature" in data["items"][2]["error"]


@pytest.mark.asyncio
async def test_batch_upload_duplicate_handling(client, sample_pdf_bytes):
    """Test that uploading a file that was already completed returns existing completed document."""
    headers = {"X-User-Id": "user_dup_tester"}

    # 1. Ingest first copy
    single_file = {"file": ("original.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    init_res = await client.post("/api/v1/documents", files=single_file, headers=headers)
    assert init_res.status_code == 201
    doc_id = init_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # 2. Batch upload containing duplicate
    files = [
        ("files", ("duplicate_copy.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
    ]
    batch_res = await client.post("/api/v1/documents/batch", files=files, headers=headers)
    assert batch_res.status_code == 201
    data = batch_res.json()

    assert data["total"] == 1
    assert data["successful_count"] == 1
    assert data["items"][0]["status"] == "completed"
    assert data["items"][0]["document"]["id"] == doc_id


@pytest.mark.asyncio
async def test_batch_upload_limit_enforcement(client, sample_pdf_bytes):
    """Test that attempting to upload more than MAX_BATCH_FILES raises validation error."""
    headers = {"X-User-Id": "user_limit_tester"}

    # Exceed limit (> 10 files)
    files = [
        ("files", (f"paper_{i}.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf"))
        for i in range(12)
    ]
    resp = await client.post("/api/v1/documents/batch", files=files, headers=headers)
    assert resp.status_code == 400
    assert "exceeds the limit" in resp.json()["detail"]


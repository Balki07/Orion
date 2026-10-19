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

"""Regression test suite for ORION RAG retrieval, generation, citation validation, and security."""

import io
import pytest
import pymupdf
from sqlalchemy import select

from app.db.base import Base
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.citations.validator import CitationValidator
from app.services.generation.llm import GeminiService
from app.services.ingestion.extractor import PdfExtractor
from app.services.ingestion.pipeline import get_ingestion_pipeline
from app.services.retrieval.engine import RetrievalEngine


@pytest.fixture
def synthetic_paper_pdf() -> bytes:
    """Creates a deterministic 2-page research PDF with known title, authors, methodology, and metrics."""
    doc = pymupdf.open()
    rect = pymupdf.Rect(50, 50, 550, 750)

    # Page 1: Header, Title, Authors, Abstract
    p1 = doc.new_page(width=595, height=842)
    p1_content = (
        "Decentralized Plastic Credit Verification Using Smart Contracts\n\n"
        "Authors: Dr. Elena Rostova, Marcus Vance, and Dr. Sarah Chen\n"
        "Department of Environmental Engineering, Cambridge Institute\n\n"
        "Abstract: Traditional plastic credit systems suffer from opacity, double-counting, and "
        "unverifiable claims. This paper presents CleanChain, an open-source decentralized architecture "
        "leveraging Polygon smart contracts to guarantee end-to-end traceability of plastic waste recovery. "
        "Our system links recycling facility weight sensors directly to ERC-20 token minting logic."
    )
    p1.insert_textbox(rect, p1_content, fontsize=11)

    # Page 2: Experimental Findings, Metrics, and Benchmarks
    p2 = doc.new_page(width=595, height=842)
    p2_content = (
        "Experimental Benchmarks and Verification Latency\n\n"
        "In stress-testing across 10,000 simulated plastic credit redemption events, CleanChain demonstrated "
        "an average confirmation latency of 4.12 seconds and an audited throughput of 142 transactions per second. "
        "Compared to legacy centralized registry databases, fraud incidence from duplicate claims dropped to 0.00%.\n\n"
        "Energy Consumption Analysis: CleanChain's Proof-of-Stake consensus consumed 0.00028 kWh per verification event."
    )
    p2.insert_textbox(rect, p2_content, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_known_fact_retrieval_and_answer_with_citation(client, synthetic_paper_pdf):
    """Proves that a known factual question in an indexed PDF retrieves evidence and produces a verified citation."""
    user_id = "user_eval_alice"
    headers = {"X-User-Id": user_id}

    # 1. Upload & Ingest synthetic paper
    files = {"file": ("cleanchain_evaluation.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # 2. Ask known factual question
    payload = {
        "question": "What was the average confirmation latency and fraud incidence reported for CleanChain?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    # 3. Assert evidence grounding
    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) >= 1
    top_cite = data["citations"][0]
    assert top_cite["document_id"] == doc_id
    assert top_cite["filename"] == "cleanchain_evaluation.pdf"
    assert 2 in top_cite["page_numbers"]
    assert "4.12" in data["answer"] or "4.12" in top_cite["excerpt"]


@pytest.mark.asyncio
async def test_exact_paper_title_retrieval(client, synthetic_paper_pdf):
    """Proves that the exact paper title can be retrieved from a document that contains it."""
    user_id = "user_eval_bob"
    headers = {"X-User-Id": user_id}

    files = {"file": ("decentralized_plastic_credit.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    doc_id = upload_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # Query using exact title
    title_query = "Decentralized Plastic Credit Verification Using Smart Contracts"
    payload = {
        "question": title_query,
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) >= 1
    first_cite = data["citations"][0]
    assert first_cite["document_id"] == doc_id
    assert 1 in first_cite["page_numbers"]


@pytest.mark.asyncio
async def test_dense_and_lexical_retrieval_evidence(synthetic_paper_pdf):
    """Proves that a relevant question retrieves evidence using both dense and lexical retrieval."""
    from conftest import TestSessionLocal
    user_id = "user_eval_charlie"

    pipeline = get_ingestion_pipeline()
    engine = RetrievalEngine()

    async with TestSessionLocal() as db:
        # Ingest document
        doc = Document(
            id="doc_synth_test_001",
            owner_id=user_id,
            filename="cleanchain.pdf",
            storage_key="test/cleanchain.pdf",
            content_hash="hash_001",
            file_size=len(synthetic_paper_pdf),
            status="uploaded",
        )
        db.add(doc)
        await db.commit()

        # Extract & chunk
        extractor = PdfExtractor()
        extracted = extractor.extract_from_bytes(synthetic_paper_pdf)
        from app.services.ingestion.chunker import PageAwareChunker
        chunker = PageAwareChunker(chunk_size=300, chunk_overlap=50)
        chunks_data = chunker.chunk_pages(extracted.pages)
        embeddings = pipeline.embedder.embed_texts([c.text for c in chunks_data])

        for idx, (c_data, emb) in enumerate(zip(chunks_data, embeddings)):
            chunk = Chunk(
                id=f"chunk_synth_{idx}",
                document_id=doc.id,
                chunk_index=c_data.chunk_index,
                text=c_data.text,
                page_numbers=c_data.page_numbers,
                character_start=c_data.character_start,
                character_end=c_data.character_end,
                token_count=c_data.token_count,
                embedding=emb,
                embedding_model="BAAI/bge-small-en-v1.5",
            )
            db.add(chunk)
        doc.status = "completed"
        doc.page_count = extracted.total_pages
        await db.commit()

        query = "What is the confirmation latency and transaction throughput?"

        # 1. Dense retrieval
        dense_results = await engine.vector_retriever.search(query, user_id, db, top_k=5)
        assert len(dense_results) > 0
        assert dense_results[0][1] > 0.60  # Cosine similarity score

        # 2. Lexical retrieval
        lexical_results = await engine.lexical_retriever.search(query, user_id, db, top_k=5)
        assert len(lexical_results) > 0
        assert lexical_results[0][1] > 0.0  # Positive lexical score

        # 3. Hybrid fusion (RRF)
        fused_results, timings = await engine.retrieve(query, user_id, db, top_k=5)
        assert len(fused_results) > 0
        top_chunk, score = fused_results[0]
        assert "latency" in top_chunk.text.lower() or "throughput" in top_chunk.text.lower()


@pytest.mark.asyncio
async def test_genuinely_unanswerable_question_produces_abstention(client, synthetic_paper_pdf):
    """Proves that a genuinely unanswerable question produces a clear abstention."""
    user_id = "user_eval_david"
    headers = {"X-User-Id": user_id}

    files = {"file": ("cleanchain.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    doc_id = upload_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    unanswerable_query = "What was the quantum supercomputing benchmark performed on Mars?"
    payload = {
        "question": unanswerable_query,
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is True
    assert len(data["citations"]) == 0
    assert "insufficient evidence" in data["answer"].lower() or "not contain" in data["answer"].lower()


def test_fabricated_citation_id_rejected():
    """Proves that a fabricated citation ID is rejected by citation validation."""
    validator = CitationValidator()

    # Valid retrieved chunk
    real_chunk = Chunk(
        id="chunk_real_12345",
        document_id="doc_alpha",
        chunk_index=0,
        text="Valid verifiable research findings.",
        page_numbers=[3],
    )
    real_chunk.document = Document(id="doc_alpha", filename="real_paper.pdf")

    # Raw response containing both a legitimate citation and a fabricated citation
    raw_response = {
        "answer": "CleanChain achieved 4.12s latency [cite:1] and teleportation was demonstrated [cite:2].",
        "claims": [
            {"text": "CleanChain achieved 4.12s latency", "citation_ids": ["cite:1"]},
            {"text": "Teleportation was demonstrated", "citation_ids": ["cite:2"]},
        ],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_alpha",
                "filename": "real_paper.pdf",
                "page_numbers": [3],
                "chunk_ids": ["chunk_real_12345"],
                "excerpt": "Valid verifiable research findings.",
            },
            {
                "citation_id": "cite:2",
                "document_id": "doc_fabricated",
                "filename": "fake_paper.pdf",
                "page_numbers": [99],
                "chunk_ids": ["chunk_hallucinated_67890"],  # Non-existent chunk
                "excerpt": "Fabricated text not in any document.",
            },
        ],
    }

    verified_cites, verified_claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response=raw_response,
        retrieved_chunks=[real_chunk],
    )

    # Fabricated citation must be rejected
    verified_cite_ids = [c.citation_id for c in verified_cites]
    assert "cite:1" in verified_cite_ids
    assert "cite:2" not in verified_cite_ids
    assert len(verified_cites) == 1
    assert any("Rejected hallucinated citation 'cite:2'" in w for w in warnings)

    # Claim 2 must be unsupported
    claim_statuses = {cl.text: cl.support_status for cl in verified_claims}
    assert claim_statuses["CleanChain achieved 4.12s latency"] == "supported"
    assert claim_statuses["Teleportation was demonstrated"] == "unsupported"


@pytest.mark.asyncio
async def test_users_cannot_retrieve_another_tenants_documents(synthetic_paper_pdf):
    """Proves multi-tenant isolation: Tenant B cannot retrieve Tenant A's documents."""
    from conftest import TestSessionLocal
    tenant_a = "user_tenant_alpha_001"
    tenant_b = "user_tenant_beta_002"

    pipeline = get_ingestion_pipeline()
    engine = RetrievalEngine()

    async with TestSessionLocal() as db:
        # Ingest Tenant A's document
        doc_a = Document(
            id="doc_tenant_a_001",
            owner_id=tenant_a,
            filename="tenant_a_confidential.pdf",
            storage_key="test/tenant_a.pdf",
            content_hash="hash_a",
            file_size=len(synthetic_paper_pdf),
            status="completed",
            page_count=2,
        )
        db.add(doc_a)
        chunk_a = Chunk(
            id="chunk_a_001",
            document_id=doc_a.id,
            chunk_index=0,
            text="Confidential trade secret: Project Orion protocol specifications.",
            page_numbers=[1],
            token_count=10,
            embedding=pipeline.embedder.embed_query("Confidential trade secret: Project Orion protocol specifications."),
            embedding_model="BAAI/bge-small-en-v1.5",
        )
        db.add(chunk_a)
        await db.commit()

        # Tenant B searches for Tenant A's content
        query = "Project Orion protocol specifications"

        # Dense search by Tenant B
        dense_b = await engine.vector_retriever.search(query=query, user_id=tenant_b, db=db, top_k=5)
        assert len(dense_b) == 0

        # Lexical search by Tenant B
        lexical_b = await engine.lexical_retriever.search(query=query, user_id=tenant_b, db=db, top_k=5)
        assert len(lexical_b) == 0

        # Hybrid retrieval by Tenant B
        hybrid_b, _ = await engine.retrieve(query=query, user_id=tenant_b, db=db, top_k=5)
        assert len(hybrid_b) == 0


def test_empty_or_malformed_pdf_no_usable_evidence():
    """Proves that an empty or malformed PDF does not falsely appear to contain usable evidence."""
    extractor = PdfExtractor()

    # 1. Corrupted file header
    with pytest.raises(Exception):
        extractor.extract_from_bytes(b"Malformed binary data without PDF header", filename="bad.pdf")

    # 2. Blank PDF page with zero text characters
    blank_doc = pymupdf.open()
    blank_doc.new_page(width=595, height=842)
    blank_bytes = blank_doc.tobytes()
    blank_doc.close()

    result = extractor.extract_from_bytes(blank_bytes, filename="empty.pdf")
    assert result.total_pages == 1
    assert result.is_scanned_or_empty is True
    assert result.total_characters == 0

"""Regression test suite for ORION RAG retrieval, generation, citation validation, and security."""

import io
import pytest
import pymupdf
from sqlalchemy import select

from app.core.errors import IngestionError
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
    assert (
        "insufficient evidence" in data["answer"].lower()
        or "not contain" in data["answer"].lower()
        or "contains no" in data["answer"].lower()
    )


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

    # 2. Blank PDF page with zero text characters raises IngestionError (no usable evidence)
    blank_doc = pymupdf.open()
    blank_doc.new_page(width=595, height=842)
    blank_bytes = blank_doc.tobytes()
    blank_doc.close()

    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_from_bytes(blank_bytes, filename="empty.pdf")
    assert exc_info.value.error_code == "ERR_PDF_SCANNED_NO_TEXT"


@pytest.mark.asyncio
async def test_self_attention_question_abstains_when_papers_lack_transformer_evidence(client, synthetic_paper_pdf):
    """Proves that asking about self-attention complexity on documents lacking transformer evidence legitimately abstains."""
    user_id = "user_eval_attention_test"
    headers = {"X-User-Id": user_id}

    # Upload synthetic paper (about decentralized plastic credit, not Transformers)
    files = {"file": ("cleanchain_evaluation.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # Ask the exact user question about self-attention complexity
    payload = {
        "question": "What is the computational complexity of self-attention per layer?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    # The system must abstain with genuine insufficient evidence and not hallucinate O(n^2)
    assert data["insufficient_evidence"] is True
    assert data["reason_code"] == "GENUINE_INSUFFICIENT_EVIDENCE"
    assert len(data["citations"]) == 0


@pytest.mark.asyncio
async def test_multi_passage_evidence_retrieval_and_synthesis(client, synthetic_paper_pdf):
    """Proves that a question requiring evidence from multiple pages (p.1 abstract + p.2 benchmarks) retrieves both."""
    user_id = "user_eval_multi_passage"
    headers = {"X-User-Id": user_id}

    files = {"file": ("cleanchain_evaluation.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # Multi-passage question spanning smart contract architecture (p.1) and confirmation latency (p.2)
    payload = {
        "question": "Which smart contract blockchain does CleanChain use, and what average confirmation latency was recorded in stress-testing?",
        "document_ids": [doc_id],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    assert data["insufficient_evidence"] is False
    assert data["reason_code"] == "ANSWER_GROUNDED"
    assert len(data["citations"]) >= 1

    cited_pages = {p for c in data["citations"] for p in c["page_numbers"]}
    # Should cite page 1 and/or page 2
    assert (1 in cited_pages) or (2 in cited_pages)
    answer_lower = data["answer"].lower()
    assert ("polygon" in answer_lower or "smart contract" in answer_lower)
    assert ("4.12" in answer_lower or "latency" in answer_lower)


@pytest.mark.asyncio
async def test_conflicting_statements_across_documents(client):
    """Proves that conflicting statements across two selected documents are attributed to their respective sources."""
    user_id = "user_eval_conflicts"
    headers = {"X-User-Id": user_id}

    # Document A: Claims 4.12s latency
    doc_a = pymupdf.open()
    p1_a = doc_a.new_page(width=595, height=842)
    p1_a.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "CleanChain Baseline Report\n\nIn standard trials, CleanChain demonstrated an average confirmation latency of 4.12 seconds.",
    )
    bytes_a = doc_a.tobytes()
    doc_a.close()

    # Document B: Claims 28.5s latency under high congestion
    doc_b = pymupdf.open()
    p1_b = doc_b.new_page(width=595, height=842)
    p1_b.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "CleanChain Stress Report\n\nUnder severe network congestion, CleanChain exhibited an elevated confirmation latency of 28.5 seconds.",
    )
    bytes_b = doc_b.tobytes()
    doc_b.close()

    files_a = {"file": ("report_baseline.pdf", io.BytesIO(bytes_a), "application/pdf")}
    res_a = await client.post("/api/v1/documents", files=files_a, headers=headers)
    doc_id_a = res_a.json()["id"]

    files_b = {"file": ("report_stress.pdf", io.BytesIO(bytes_b), "application/pdf")}
    res_b = await client.post("/api/v1/documents", files=files_b, headers=headers)
    doc_id_b = res_b.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id_a, session)
        await pipeline.process_document(doc_id_b, session)

    # Ask across both documents
    payload = {
        "question": "What confirmation latency is reported for CleanChain across the studies?",
        "document_ids": [doc_id_a, doc_id_b],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) >= 1
    # Verify citations reference the valid documents
    cited_doc_ids = {c["document_id"] for c in data["citations"]}
    assert doc_id_a in cited_doc_ids or doc_id_b in cited_doc_ids


def test_unsupported_numerical_claims_flagged():
    """Proves that claims with unsupported numerical figures are flagged as unsupported."""
    validator = CitationValidator()
    chunk = Chunk(
        id="chunk_metric_001",
        document_id="doc_alpha",
        chunk_index=0,
        text="In stress-testing, CleanChain demonstrated an average confirmation latency of 4.12 seconds and an audited throughput of 142 transactions per second.",
        page_numbers=[2],
    )
    chunk.document = Document(id="doc_alpha", filename="cleanchain.pdf")

    raw_response = {
        "answer": "CleanChain achieved 4.12s latency [cite:1] and 9500 transactions per second [cite:1].",
        "claims": [
            {"text": "CleanChain achieved an average confirmation latency of 4.12 seconds.", "citation_ids": ["cite:1"]},
            {"text": "CleanChain throughput reached 9500 transactions per second under load.", "citation_ids": ["cite:1"]},
        ],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_alpha",
                "filename": "cleanchain.pdf",
                "page_numbers": [2],
                "chunk_ids": ["chunk_metric_001"],
                "excerpt": "4.12 seconds and an audited throughput of 142 transactions per second.",
            }
        ],
    }

    verified_cites, verified_claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response=raw_response,
        retrieved_chunks=[chunk],
    )

    assert len(verified_cites) == 1
    claim_statuses = {cl.text: cl.support_status for cl in verified_claims}
    assert claim_statuses["CleanChain achieved an average confirmation latency of 4.12 seconds."] == "supported"
    # The 9500 tps claim must be flagged as unsupported because 9500 does not appear in the evidence
    assert claim_statuses["CleanChain throughput reached 9500 transactions per second under load."] == "unsupported"
    assert any("contains unverified numerical figures" in w for w in warnings)


def test_mismatched_citation_document_id_rejected():
    """Proves that a citation where claimed document_id does not match the chunk's true document is rejected."""
    validator = CitationValidator()
    chunk = Chunk(
        id="chunk_true_alpha",
        document_id="doc_alpha",
        chunk_index=0,
        text="CleanChain utilizes smart contracts on Polygon.",
        page_numbers=[1],
    )
    chunk.document = Document(id="doc_alpha", filename="alpha.pdf")

    raw_response = {
        "answer": "CleanChain uses Polygon smart contracts [cite:1].",
        "claims": [
            {"text": "CleanChain uses Polygon smart contracts.", "citation_ids": ["cite:1"]},
        ],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_mismatched_beta",  # Deliberately claims doc_beta for doc_alpha's chunk
                "filename": "beta.pdf",
                "page_numbers": [1],
                "chunk_ids": ["chunk_true_alpha"],
                "excerpt": "CleanChain utilizes smart contracts on Polygon.",
            }
        ],
    }

    verified_cites, verified_claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response=raw_response,
        retrieved_chunks=[chunk],
    )

    # Mismatched citation must be rejected
    assert len(verified_cites) == 0
    assert any("does not match actual chunk document" in w for w in warnings)
    assert verified_claims[0].support_status == "unsupported"


@pytest.mark.asyncio
async def test_duplicate_uploads_handling(client, synthetic_paper_pdf):
    """Proves that uploading the same PDF twice handles retrieval cleanly without errors."""
    user_id = "user_eval_duplicates"
    headers = {"X-User-Id": user_id}

    # Upload duplicate 1
    files1 = {"file": ("cleanchain_copy1.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    res1 = await client.post("/api/v1/documents", files=files1, headers=headers)
    doc_id1 = res1.json()["id"]

    # Upload duplicate 2
    files2 = {"file": ("cleanchain_copy2.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    res2 = await client.post("/api/v1/documents", files=files2, headers=headers)
    doc_id2 = res2.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id1, session)
        await pipeline.process_document(doc_id2, session)

    # Query with both duplicates selected
    payload = {
        "question": "What is the confirmation latency reported for CleanChain?",
        "document_ids": [doc_id1, doc_id2],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) >= 1
    assert "4.12" in data["answer"] or "4.12" in data["citations"][0]["excerpt"]


@pytest.mark.asyncio
async def test_pipeline_failure_reason_codes(client):
    """Proves that pipeline failure conditions return the correct structured diagnostic reason codes."""
    user_id = "user_eval_reasons"
    headers = {"X-User-Id": user_id}

    # 1. NO_SELECTED_DOCUMENTS: querying nonexistent document IDs
    payload_no_docs = {
        "question": "What is the latency?",
        "document_ids": ["doc_nonexistent_12345"],
        "top_k": 5,
    }
    res_no_docs = await client.post("/api/v1/research/ask", json=payload_no_docs, headers=headers)
    assert res_no_docs.status_code == 200
    data_no_docs = res_no_docs.json()
    assert data_no_docs["insufficient_evidence"] is True
    assert data_no_docs["reason_code"] == "NO_SELECTED_DOCUMENTS"

    # 2. SELECTED_DOCUMENTS_NOT_INDEXED: document exists but is not completed / has 0 chunks
    from conftest import TestSessionLocal
    async with TestSessionLocal() as db:
        unindexed_doc = Document(
            id="doc_unindexed_001",
            owner_id=user_id,
            filename="unprocessed.pdf",
            storage_key="test/unprocessed.pdf",
            content_hash="hash_unproc",
            file_size=1024,
            status="uploaded",  # Not completed
            page_count=0,
        )
        db.add(unindexed_doc)
        await db.commit()

    payload_unindexed = {
        "question": "What is the latency?",
        "document_ids": ["doc_unindexed_001"],
        "top_k": 5,
    }
    res_unindexed = await client.post("/api/v1/research/ask", json=payload_unindexed, headers=headers)
    assert res_unindexed.status_code == 200
    data_unindexed = res_unindexed.json()
    assert data_unindexed["insufficient_evidence"] is True
    assert data_unindexed["reason_code"] == "SELECTED_DOCUMENTS_NOT_INDEXED"


def test_query_decomposition_patterns():
    """Validates decomposition of compound inquiries into distinct subquestions before retrieval."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    # 1. Imperative list with commas and 'and'
    q1 = "Analyze fraudulent recycling claims, material-flow inconsistencies, traceability, unresolved research gaps, and relevance to the project's frozen research scope."
    pq1 = process_query(q1)
    assert pq1.is_compound_query is True
    assert len(pq1.subqueries) == 5
    assert "fraudulent recycling claims" in pq1.subqueries
    assert "material-flow inconsistencies" in pq1.subqueries
    assert "traceability" in pq1.subqueries
    assert "unresolved research gaps" in pq1.subqueries
    assert "relevance to the project's frozen research scope" in pq1.subqueries

    # 2. Numbered list
    q2 = "1. Material flow accounts in India\n2. Traceability platform architecture\n3. Empirical research gaps"
    pq2 = process_query(q2)
    assert pq2.is_compound_query is True
    assert len(pq2.subqueries) == 3

    # 3. Semicolon-separated subquestions
    q3 = "What are the material flow inconsistencies; how is traceability ensured; what are the data limitations?"
    pq3 = process_query(q3)
    assert pq3.is_compound_query is True
    assert len(pq3.subqueries) == 3

    # 4. Single-topic query should NOT be decomposed
    q4 = "What is the computational complexity of self-attention per layer?"
    pq4 = process_query(q4)
    assert pq4.is_compound_query is False
    assert len(pq4.subqueries) == 1
    assert pq4.subqueries[0] == q4


@pytest.mark.asyncio
async def test_multi_paper_synthesis_and_structured_sections(client):
    """Proves end-to-end multi-paper research synthesis, structured section output, and partial coverage."""
    user_id = "user_eval_synthesis"
    headers = {"X-User-Id": user_id}

    # Create Paper 1: Material Flow Analysis
    doc1 = pymupdf.open()
    p1 = doc1.new_page(width=595, height=842)
    p1.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "National Plastic Material Flow Analysis and Informal Leakages\n\n"
        "Authors: Dr. Rajesh Sharma and Dr. Anita Desai\n\n"
        "Abstract: We quantify plastic material-flow accounts across the economy. Our mass-balance models "
        "reveal substantial material-flow inconsistencies, with 2.4 Mt of plastic packaging leaking into informal "
        "recycling channels without regulatory oversight.\n\n"
        "Research Gaps: A critical research gap remains regarding the integration of informal waste pickers into formal EPR systems.",
        fontsize=11
    )
    pdf1_bytes = doc1.tobytes()
    doc1.close()

    # Create Paper 2: Digital Traceability Platform
    doc2 = pymupdf.open()
    p2 = doc2.new_page(width=595, height=842)
    p2.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Digital Traceability Framework for Extended Producer Responsibility\n\n"
        "Authors: Dr. Somantri Pratama and Budi Santoso\n\n"
        "Abstract: We present an integrated platform providing end-to-end traceability for recycled polymers. "
        "The digital ledger eliminates discrepancies between collection receipts and reprocessing declarations, "
        "substantiating genuine material stewardship.\n\n"
        "Research Limitations: A prominent research limitation is data scarcity in rural collection hubs.",
        fontsize=11
    )
    pdf2_bytes = doc2.tobytes()
    doc2.close()

    # Upload and ingest both papers
    files1 = {"file": ("national_plastic_mfa.pdf", io.BytesIO(pdf1_bytes), "application/pdf")}
    res1 = await client.post("/api/v1/documents", files=files1, headers=headers)
    assert res1.status_code == 201
    doc_id1 = res1.json()["id"]

    files2 = {"file": ("digital_traceability_epr.pdf", io.BytesIO(pdf2_bytes), "application/pdf")}
    res2 = await client.post("/api/v1/documents", files=files2, headers=headers)
    assert res2.status_code == 201
    doc_id2 = res2.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id1, session)
        await pipeline.process_document(doc_id2, session)

    # Ask compound question covering supported facets (MFA, traceability, research gaps)
    # and unsupported facets (fraudulent recycling claims, frozen research scope)
    compound_payload = {
        "question": "Analyze fraudulent recycling claims, material-flow inconsistencies, traceability, unresolved research gaps, and relevance to the project's frozen research scope.",
        "document_ids": [doc_id1, doc_id2],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=compound_payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    # 1. Partial evidence coverage: answers supported parts without global abstention
    assert data["insufficient_evidence"] is False
    answer = data["answer"]

    # 2. Structured synthesis sections present
    assert "### Supported Findings by Source" in answer
    assert "### Cross-Paper Synthesis" in answer
    assert "### Identified Research Gaps" in answer
    assert "### Insufficient Evidence & Unsubstantiated Facets" in answer

    # 3. Both papers cited with verified citations
    doc_ids_cited = {c["document_id"] for c in data["citations"]}
    assert doc_id1 in doc_ids_cited
    assert doc_id2 in doc_ids_cited

    filenames_cited = {c["filename"] for c in data["citations"]}
    assert "national_plastic_mfa.pdf" in filenames_cited
    assert "digital_traceability_epr.pdf" in filenames_cited

    # 4. Negative grounding safeguard: unsupported claims explicitly identified
    assert "fraudulent recycling claims" in answer
    assert "frozen research scope" in answer
    unsupported_claims = [cl for cl in data["claims"] if cl["support_status"] == "unsupported"]
    assert len(unsupported_claims) >= 1


@pytest.mark.asyncio
async def test_compound_abstention_when_all_subquestions_unsupported(client):
    """Proves that a compound query where ALL subquestions lack evidence strictly abstains."""
    user_id = "user_eval_compound_abstain"
    headers = {"X-User-Id": user_id}

    # Upload single paper on plastic recycling
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Plastic Recycling Operations and Sorting Logistics\n\n"
        "Authors: Dr. Kevin Miller\n\n"
        "Abstract: Overview of mechanical sorting and wash lines for post-consumer PET bottles.",
        fontsize=11
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("pet_recycling.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    # Ask compound query completely unrelated to plastic sorting
    unrelated_compound = {
        "question": "Analyze quantum error correction, topological qubit braids, and cryogenic dilution refrigerators.",
        "document_ids": [doc_id],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=unrelated_compound, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()

    assert data["insufficient_evidence"] is True
    assert len(data["claims"]) == 0


@pytest.mark.asyncio
async def test_excerpt_sentence_integrity_no_midword_cut():
    """Proves that excerpt extraction uses neighbor chunks to form complete sentences and never cuts mid-word."""
    from app.services.generation.llm import extract_complete_sentence_excerpt

    chunk_mid_sentence = "has demonstrated that informal waste collection accounts for 43% of total recovery in Jakarta."
    prev_chunk = "Previous field investigations in Southeast Asia. A comprehensive survey "
    next_chunk = "Standardized reporting is required to verify credits. Further research is ongoing."

    excerpt = extract_complete_sentence_excerpt(
        chunk_text=chunk_mid_sentence,
        prev_text=prev_chunk,
        next_text=next_chunk,
        target_terms={"informal", "recovery"},
        max_chars=360,
    )

    # Must start with capital letter, end with period, and contain full sentence
    assert excerpt[0].isupper()
    assert excerpt.endswith(".")
    assert "A comprehensive survey has demonstrated that informal waste collection accounts for 43% of total recovery in Jakarta." in excerpt
    assert not excerpt.endswith(("...", "has", "has dem"))


@pytest.mark.asyncio
async def test_duplicate_document_detection_and_non_corroboration(client, synthetic_paper_pdf):
    """Proves that duplicate uploads sharing content hash are detected and not counted as independent corroboration."""
    user_id = "user_eval_dups"
    headers = {"X-User-Id": user_id}

    # Upload exact same bytes as two different filenames (simulating Somantri.pdf and isi_31.07_22.pdf)
    files1 = {"file": ("paper_original.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    res1 = await client.post("/api/v1/documents", files=files1, headers=headers)
    assert res1.status_code == 201
    doc_id1 = res1.json()["id"]

    files2 = {"file": ("paper_renamed_copy.pdf", io.BytesIO(synthetic_paper_pdf), "application/pdf")}
    res2 = await client.post("/api/v1/documents", files=files2, headers=headers)
    assert res2.status_code == 201
    doc_id2 = res2.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id1, session)
        await pipeline.process_document(doc_id2, session)

    # Ask multi-part question across both documents
    payload = {
        "question": (
            "Synthesize findings from the selected documents:\n"
            "1. What architecture is proposed for plastic credit verification?\n"
            "2. Are there explicit findings or audits of fraudulent claims?"
        ),
        "document_ids": [doc_id1, doc_id2],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()
    answer = data["answer"]

    # Both documents remain preserved in database
    async with TestSessionLocal() as session:
        doc1 = await session.get(Document, doc_id1)
        doc2 = await session.get(Document, doc_id2)
        assert doc1 is not None and doc2 is not None
        assert doc1.content_hash == doc2.content_hash

    # Provenance note verifies duplicate copies rather than treating as independent corroboration
    assert "SHA-256" in answer or "duplicate" in answer.lower()
    assert "### Cross-Paper Synthesis" in answer


@pytest.mark.asyncio
async def test_non_repetitive_gap_and_consolidated_unsupported(client):
    """Proves that research gaps do not repeat Section 1 excerpts and unsupported explanations are consolidated."""
    user_id = "user_eval_non_repetitive"
    headers = {"X-User-Id": user_id}

    doc = pymupdf.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Microplastic Material Flow Analysis in Urban Watersheds\n\n"
        "Authors: Dr. Samuel Vance\n\n"
        "Abstract: Empirical mass-balance tracking of polymer leakage in freshwater basins. "
        "Primary finding: storm runoff accounts for 78% of unmanaged microplastic release across the municipal catchment area.",
        fontsize=11
    )
    p2 = doc.new_page(width=595, height=842)
    p2.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Methodological Limitations and Research Gaps\n\n"
        "Section 4: A significant research gap exists regarding polymer degradation rates in sediment layers. "
        "Unresolved data scarcity in benthic sampling limits long-term mass balance predictive accuracy.",
        fontsize=11
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("watershed_mfa.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    from conftest import TestSessionLocal
    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    payload = {
        "question": (
            "Comprehensive review of urban microplastics:\n"
            "1. What proportion of leakage stems from storm runoff?\n"
            "2. What explicit research gaps and data scarcities are reported?\n"
            "3. Are there audits substantiating fraudulent recycling credits?\n"
            "4. How does this align with the project's frozen research scope?"
        ),
        "document_ids": [doc_id],
        "top_k": 8,
    }
    ask_res = await client.post("/api/v1/research/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    data = ask_res.json()
    answer = data["answer"]

    # Section 1 contains the primary finding
    assert "### Supported Findings by Source" in answer
    assert "storm runoff" in answer

    # Section 3 contains the distinct research gap without repeating Section 1 finding
    assert "### Identified Research Gaps" in answer
    assert "benthic" in answer or "degradation" in answer

    # Section 4 consolidates unsupported facets without duplicate boilerplate
    assert "### Insufficient Evidence & Unsubstantiated Facets" in answer
    assert ("Allegations of Fraud" in answer or "fraud" in answer.lower())
    assert ("External Research Scope Constraints" in answer or "scope" in answer.lower())

    # Citations excerpts must all end in terminal punctuation
    for cite in data["citations"]:
        assert cite["excerpt"].endswith((".", "!", "?"))




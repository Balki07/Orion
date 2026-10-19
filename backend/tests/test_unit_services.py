"""Unit tests covering PDF extraction, chunking, embeddings, citation validation, and security."""

import pytest
from app.core.errors import FileValidationError, UnauthorizedAccessError
from app.models.chunk import Chunk
from app.models.document import Document
from app.security.permissions import verify_ownership
from app.services.citations.validator import CitationValidator
from app.services.ingestion.chunker import PageAwareChunker
from app.services.ingestion.embedder import LocalEmbedder
from app.services.ingestion.extractor import PdfExtractor


def test_pdf_extraction(sample_pdf_bytes):
    """Verify PyMuPDF extracts pages with exact page-by-page provenance."""
    extractor = PdfExtractor(max_pages=10)
    result = extractor.extract_from_bytes(sample_pdf_bytes, filename="attention.pdf")

    assert result.total_pages == 2
    assert not result.is_scanned_or_empty
    assert len(result.pages) == 2

    p1 = result.pages[0]
    assert p1.page_number == 1
    assert "Attention Is All You Need" in p1.text
    assert p1.character_count > 100

    p2 = result.pages[1]
    assert p2.page_number == 2
    assert "Scaled Dot-Product Attention" in p2.text
    assert "BLEU score of 28.4" in p2.text


def test_pdf_extraction_invalid_header():
    """Verify corrupted files missing %PDF- are rejected."""
    extractor = PdfExtractor(max_pages=10)
    with pytest.raises(Exception) as exc_info:
        extractor.extract_from_bytes(b"NOT A REAL PDF FILE HEADER", filename="fake.pdf")
    assert "PDF" in str(exc_info.value)


def test_page_aware_chunking(sample_pdf_bytes):
    """Verify that chunking preserves contributing page numbers and boundaries."""
    extractor = PdfExtractor(max_pages=10)
    extracted = extractor.extract_from_bytes(sample_pdf_bytes)

    chunker = PageAwareChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_pages(extracted.pages)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.text.strip()
        assert len(chunk.page_numbers) >= 1
        assert all(p in [1, 2] for p in chunk.page_numbers)
        assert chunk.token_count > 0


def test_embedding_dimensions():
    """Verify embedding generator produces 384-dimensional normalized vectors."""
    embedder = LocalEmbedder(dimensions=384)
    texts = [
        "Self-attention connects all pairs of positions in a sequence.",
        "Convolutional layers have a fixed receptive field.",
    ]
    vectors = embedder.embed_texts(texts)

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384

    # Query embedding
    q_vec = embedder.embed_query("What is self-attention?")
    assert len(q_vec) == 384


def test_citation_validation_and_claim_support():
    """Verify citation validator verifies real chunk IDs and rejects hallucinated IDs."""
    validator = CitationValidator()

    # Create mock chunk and document
    doc = Document(id="doc_1", owner_id="user_1", filename="transformer.pdf", storage_key="k1", content_hash="h1", file_size=100)
    chunk1 = Chunk(id="chunk_1", document_id="doc_1", chunk_index=0, text="Scaled Dot-Product Attention equation.", page_numbers=[2], character_start=0, character_end=50, token_count=10)
    chunk1.document = doc

    raw_response = {
        "answer": "The attention is computed via Scaled Dot-Product [cite:1].",
        "claims": [
            {"text": "Attention is computed via Scaled Dot-Product", "citation_ids": ["cite:1"]},
            {"text": "Quantum entanglement was leveraged", "citation_ids": ["cite:hallucinated"]},
        ],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_1",
                "filename": "fake_name.pdf",  # Should be overridden by trusted database record
                "page_numbers": [999],        # Should be hydrated from real chunk
                "chunk_ids": ["chunk_1"],
                "excerpt": "Scaled Dot-Product Attention equation.",
            },
            {
                "citation_id": "cite:hallucinated",
                "document_id": "doc_imaginary",
                "chunk_ids": ["chunk_imaginary_999"],
            },
        ],
        "insufficient_evidence": False,
        "warnings": [],
    }

    verified_citations, verified_claims, warnings, insufficient_ev = (
        validator.validate_and_hydrate(raw_response, [chunk1])
    )

    # 1. cite:1 should be verified with trusted filename and page numbers
    assert len(verified_citations) == 1
    assert verified_citations[0].citation_id == "cite:1"
    assert verified_citations[0].filename == "transformer.pdf"  # Overridden with real DB record
    assert verified_citations[0].page_numbers == [2]          # Overridden with real DB record

    # 2. Claim with cite:1 is supported, claim with cite:hallucinated is unsupported
    assert len(verified_claims) == 2
    assert verified_claims[0].support_status == "supported"
    assert verified_claims[1].support_status == "unsupported"

    # 3. Warning emitted for rejected hallucination
    assert any("cite:hallucinated" in w for w in warnings)


def test_ownership_authorization():
    """Verify strict tenant isolation and access denial."""
    # Matching owner
    verify_ownership(resource_owner_id="user_alice", current_user_id="user_alice")

    # Mismatched owner
    with pytest.raises(UnauthorizedAccessError):
        verify_ownership(resource_owner_id="user_alice", current_user_id="user_bob")

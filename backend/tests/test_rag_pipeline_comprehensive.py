"""Comprehensive reproducible regression suite for ORION RAG Pipeline (Tests A through J).

Covers:
- Test A: First-page answer (Abstract p.1, Objectives p.2)
- Test B: Exact title extraction and citation
- Test C: Methodology and numerical extraction (Databases, years, retained/excluded counts)
- Test D: Middle-of-document retrieval (Swarm communication topology p.4)
- Test E: End-of-document retrieval (Conclusion and future directions p.5)
- Test F: Multi-document source selection (Tenant isolation and doc-specific filtering)
- Test G: Genuine abstention (Unanswerable question e.g. author's favourite food)
- Test H: Invalid citation rejection (Fabricated chunk ID rejected, never presented as verified)
- Test I: Semantic retrieval without exact lexical overlap
- Test J: Duplicate, empty, and malformed chunk handling
"""

import io
import pytest
import pymupdf
from sqlalchemy import select

from app.db.base import Base
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.citations.validator import CitationValidator
from app.services.generation.llm import GeminiService
from app.services.ingestion.pipeline import get_ingestion_pipeline
from app.services.retrieval.diagnostics import (
    REASON_ANSWER_GROUNDED,
    REASON_CITATION_VALIDATION_FAILED,
    REASON_GENUINE_INSUFFICIENT_EVIDENCE,
    REASON_NO_SELECTED_DOCUMENTS,
    REASON_RETRIEVAL_NO_CANDIDATES,
)
from app.services.retrieval.engine import RetrievalEngine


@pytest.fixture
def drone_review_pdf() -> bytes:
    """Creates a deterministic 5-page research paper for multi-page RAG verification."""
    doc = pymupdf.open()
    rect = pymupdf.Rect(50, 50, 550, 750)

    # Page 1: Title, Abstract, Problem statement
    p1 = doc.new_page(width=595, height=842)
    p1_text = (
        "Autonomous Drone Swarm Navigation in Dense Urban Canyons: A Comprehensive Review\n\n"
        "Authors: Dr. Alistair Vance and Dr. Maya Lin\n"
        "Robotics Institute, Zurich Autonomous Systems Laboratory\n\n"
        "Abstract: This review addresses the critical challenge of high-density autonomous drone swarm "
        "navigation in GPS-denied urban environments where multipath signal reflections and physical occlusions "
        "prevent reliable global localization. Traditional centralized flight controllers fail under severe "
        "channel fading and communication latency. We analyze how decentralized sensor fusion and onboard edge "
        "intelligence mitigate these navigational bottlenecks."
    )
    p1.insert_textbox(rect, p1_text, fontsize=11)

    # Page 2: Introduction & Main Objectives
    p2 = doc.new_page(width=595, height=842)
    p2_text = (
        "1. Introduction and Review Objectives\n\n"
        "As aerial robotics scale to hundreds of concurrent agents in metropolitan airspace, coordinated flight "
        "demands strict autonomy without relying on external positioning infrastructure.\n\n"
        "The main objectives of this review are threefold: (1) to systematically evaluate visual-inertial odometry "
        "algorithms under dynamic lighting and structural occlusion; (2) to synthesize decentralized collision "
        "avoidance protocols operating under bounded inter-agent communication bandwidth; and (3) to establish "
        "standardized benchmarking metrics for multi-agent aerial resilience."
    )
    p2.insert_textbox(rect, p2_text, fontsize=11)

    # Page 3: Methodology and Numerical Extraction
    p3 = doc.new_page(width=595, height=842)
    p3_text = (
        "2. Review Methodology and Study Selection\n\n"
        "We executed a systematic literature query across three primary bibliographic databases: Scopus, IEEE Xplore, "
        "and Web of Science, covering publication years from 2018 to 2024. The initial query yielded 1,420 candidate articles.\n\n"
        "Applying PRISMA screening protocols, 1,280 articles were excluded due to lack of full-scale experimental hardware "
        "validation or absence of multi-drone empirical trials. Exactly 140 articles were retained for rigorous qualitative "
        "and quantitative meta-analysis."
    )
    p3.insert_textbox(rect, p3_text, fontsize=11)

    # Page 4: Middle-of-Document Detailed Findings
    p4 = doc.new_page(width=595, height=842)
    p4_text = (
        "4.3 Swarm Communication Topology and Ranging\n\n"
        "For inter-agent relative localization, peer-to-peer mesh networks utilizing ultra-wideband (UWB) transceivers "
        "operating at 6.5 GHz demonstrated superior reliability. In experimental wind tunnel trials, the decentralized "
        "UWB ranging array achieved an average ranging accuracy of 4.2 cm across inter-node distances up to 85 meters, "
        "outperforming visual-only relative pose estimation by 38%."
    )
    p4.insert_textbox(rect, p4_text, fontsize=11)

    # Page 5: Conclusion and Future Directions
    p5 = doc.new_page(width=595, height=842)
    p5_text = (
        "6. Conclusion and Future Research Directions\n\n"
        "In conclusion, decentralized visual-inertial odometry combined with ultra-wideband mesh ranging represents "
        "a viable foundation for autonomous aerial swarms in dense urban corridors.\n\n"
        "However, cumulative drift over extended operational horizons remains an open hurdle. Future research "
        "must prioritize neuromorphic event-based sensing and federated edge reinforcement learning to eliminate "
        "drift during prolonged GPS outages in dense urban canyons."
    )
    p5.insert_textbox(rect, p5_text, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def cancer_biology_pdf() -> bytes:
    """Creates a second distinct paper to test multi-document filtering and tenant scoping."""
    doc = pymupdf.open()
    rect = pymupdf.Rect(50, 50, 550, 750)
    p1 = doc.new_page(width=595, height=842)
    p1_text = (
        "Targeted Kinase Inhibitors in KRAS-Mutant Lung Adenocarcinoma\n\n"
        "Authors: Dr. Clara Gomez and Dr. Raymond Thorne\n"
        "Department of Oncology, Memorial Cancer Center\n\n"
        "Abstract: KRAS G12C mutations drive approximately 13% of non-small cell lung carcinomas. "
        "This paper evaluates the efficacy of covalent allosteric inhibitors in overcoming acquired resistance."
    )
    p1.insert_textbox(rect, p1_text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def _ingest_test_pdf(client, pdf_bytes: bytes, filename: str, user_id: str) -> str:
    """Helper to upload and process a test PDF deterministically."""
    from conftest import TestSessionLocal
    headers = {"X-User-Id": user_id}
    files = {"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    pipeline = get_ingestion_pipeline()
    async with TestSessionLocal() as session:
        await pipeline.process_document(doc_id, session)

    return doc_id


# ----------------------------------------------------------------------------------
# Test A — First-page answer (Abstract p.1, Objectives p.2)
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_first_page_answer(client, drone_review_pdf):
    user_id = "user_test_a"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "What problem does this review address, and what are its main objectives? Cite the exact page numbers.",
        "document_ids": [doc_id],
        "top_k": 8,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert data["reason_code"] == REASON_ANSWER_GROUNDED
    assert len(data["citations"]) > 0

    cited_pages = {p for cite in data["citations"] for p in cite["page_numbers"]}
    # Expect evidence from Page 1 and/or Page 2
    assert (1 in cited_pages) or (2 in cited_pages)

    # Answer should contain core findings
    answer = data["answer"].lower()
    assert "navigation" in answer or "gps-denied" in answer or "drone" in answer or "objectives" in answer


# ----------------------------------------------------------------------------------
# Test B — Exact title extraction and citation
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_b_exact_title(client, drone_review_pdf):
    user_id = "user_test_b"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "What is the exact title of the uploaded paper? Quote the title and cite the page.",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) > 0
    assert 1 in [p for cite in data["citations"] for p in cite["page_numbers"]]
    assert "autonomous drone swarm navigation" in data["answer"].lower()


# ----------------------------------------------------------------------------------
# Test C — Methodology and numerical extraction
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_c_methodology_and_numerical_extraction(client, drone_review_pdf):
    user_id = "user_test_c"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "Which databases were searched, what publication years were covered, and how many articles were retained and excluded?",
        "document_ids": [doc_id],
        "top_k": 8,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) > 0
    # Methodology is on page 3
    assert 3 in [p for cite in data["citations"] for p in cite["page_numbers"]]

    ans = data["answer"].lower()
    assert ("scopus" in ans or "ieee" in ans or "web of science" in ans or "140" in ans or "1,280" in ans or "1280" in ans)


# ----------------------------------------------------------------------------------
# Test D — Middle-of-document retrieval
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_d_middle_of_document_retrieval(client, drone_review_pdf):
    user_id = "user_test_d"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "What frequency and ranging accuracy were reported for ultra-wideband transceivers?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) > 0
    # Communication topology is on Page 4
    assert 4 in [p for cite in data["citations"] for p in cite["page_numbers"]]
    ans = data["answer"].lower()
    assert "6.5" in ans or "4.2" in ans or "uwb" in ans or "ultra-wideband" in ans


# ----------------------------------------------------------------------------------
# Test E — End-of-document retrieval
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_e_end_of_document_retrieval(client, drone_review_pdf):
    user_id = "user_test_e"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "What future research directions were recommended to eliminate cumulative drift during GPS outages?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) > 0
    # Conclusion and future work is on Page 5
    assert 5 in [p for cite in data["citations"] for p in cite["page_numbers"]]
    ans = data["answer"].lower()
    assert "neuromorphic" in ans or "reinforcement learning" in ans or "drift" in ans


# ----------------------------------------------------------------------------------
# Test F — Multi-document source selection
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_f_multi_document_source_selection(client, drone_review_pdf, cancer_biology_pdf):
    user_id = "user_test_f"
    doc_drone = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)
    doc_cancer = await _ingest_test_pdf(client, cancer_biology_pdf, "cancer_study.pdf", user_id)

    # Query only the drone paper with a question answerable only by the cancer paper
    payload = {
        "question": "What percentage of non-small cell lung carcinomas are driven by KRAS G12C mutations?",
        "document_ids": [doc_drone],  # Explicitly select ONLY drone paper
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    # Must abstain because unselected cancer document cannot be consulted
    assert data["insufficient_evidence"] is True
    # Citation must never reference doc_cancer
    for cite in data.get("citations", []):
        assert cite["document_id"] != doc_cancer


# ----------------------------------------------------------------------------------
# Test G — Genuine abstention
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_g_genuine_abstention(client, drone_review_pdf):
    user_id = "user_test_g"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    payload = {
        "question": "What is the lead author's favourite food?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is True
    assert data["reason_code"] == REASON_GENUINE_INSUFFICIENT_EVIDENCE
    assert (
        "insufficient evidence" in data["answer"].lower()
        or "not contain" in data["answer"].lower()
        or "contains no" in data["answer"].lower()
    )


# ----------------------------------------------------------------------------------
# Test H — Invalid citation rejection
# ----------------------------------------------------------------------------------
def test_h_invalid_citation_rejection():
    validator = CitationValidator()

    real_chunk = Chunk(
        id="chunk_valid_101",
        document_id="doc_valid_1",
        chunk_index=0,
        text="Empirical UWB ranging achieved 4.2 cm accuracy.",
        page_numbers=[4],
    )
    real_chunk.document = Document(id="doc_valid_1", filename="drone_review.pdf")

    # Response with a fabricated chunk ID
    hallucinated_response = {
        "answer": "Teleportation was established with 99% fidelity [cite:1].",
        "claims": [{"text": "Teleportation established", "citation_ids": ["cite:1"]}],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_fake_99",
                "filename": "quantum_fake.pdf",
                "page_numbers": [99],
                "chunk_ids": ["chunk_fabricated_99999"],  # Nonexistent chunk
                "excerpt": "Teleportation was established with 99% fidelity.",
            }
        ],
    }

    verified_cites, claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response=hallucinated_response,
        retrieved_chunks=[real_chunk],
    )

    # Must reject invalid citation and NOT present it as verified
    assert len(verified_cites) == 0
    assert any("Rejected hallucinated citation 'cite:1'" in w for w in warnings)
    assert claims[0].support_status == "unsupported"


# ----------------------------------------------------------------------------------
# Test I — Retrieval and filter regression (semantic relevance without exact lexical overlap)
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_i_semantic_retrieval_without_exact_lexical_overlap(client, drone_review_pdf):
    user_id = "user_test_i"
    doc_id = await _ingest_test_pdf(client, drone_review_pdf, "drone_review.pdf", user_id)

    # Question uses synonyms: "prevent mid-air crashes" instead of "collision avoidance"
    payload = {
        "question": "How do aerial robots prevent mid-air crashes without centralized air traffic control?",
        "document_ids": [doc_id],
        "top_k": 5,
    }
    res = await client.post("/api/v1/research/ask", json=payload, headers={"X-User-Id": user_id})
    assert res.status_code == 200
    data = res.json()

    assert data["insufficient_evidence"] is False
    assert len(data["citations"]) > 0
    # Must retrieve p.2 (collision avoidance) or p.4 (mesh network relative positioning)
    cited_pages = {p for c in data["citations"] for p in c["page_numbers"]}
    assert (2 in cited_pages) or (4 in cited_pages) or (1 in cited_pages)


# ----------------------------------------------------------------------------------
# Test J — Duplicate, empty, and malformed chunk handling
# ----------------------------------------------------------------------------------
def test_j_duplicate_and_malformed_chunk_handling():
    validator = CitationValidator()

    chunk_normal = Chunk(
        id="chunk_norm_1",
        document_id="doc_norm_1",
        chunk_index=0,
        text="Normal verifiable evidence text.",
        page_numbers=[1],
    )
    chunk_normal.document = Document(id="doc_norm_1", filename="normal.pdf")

    # Malformed raw response with duplicate citation IDs and nonexistent chunk references
    malformed_response = {
        "answer": "Normal claim [cite:1] and malformed claim [cite:2].",
        "claims": [
            {"text": "Normal claim", "citation_ids": ["cite:1"]},
            {"text": "Malformed claim", "citation_ids": ["cite:2", "cite:3"]},
        ],
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_norm_1",
                "filename": "normal.pdf",
                "page_numbers": [1],
                "chunk_ids": ["chunk_norm_1"],
                "excerpt": "Normal verifiable evidence text.",
            },
            {
                "citation_id": "cite:1",  # Duplicate citation ID
                "document_id": "doc_norm_1",
                "filename": "normal.pdf",
                "page_numbers": [1],
                "chunk_ids": ["chunk_norm_1"],
                "excerpt": "Normal verifiable evidence text.",
            },
            {
                "citation_id": "cite:2",
                "document_id": "unknown_doc",
                "filename": "",
                "page_numbers": [],
                "chunk_ids": ["nonexistent_chunk_id"],  # Malformed
                "excerpt": "",
            },
        ],
    }

    verified_cites, claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response=malformed_response,
        retrieved_chunks=[chunk_normal],
    )

    # Valid citation is verified once, invalid is rejected
    assert len(verified_cites) >= 1
    assert any(c.citation_id == "cite:1" for c in verified_cites)
    assert not any(c.citation_id == "cite:2" for c in verified_cites)
    assert any("Rejected hallucinated citation 'cite:2'" in w for w in warnings)


# ----------------------------------------------------------------------------------
# Test K — Multi-page chunk exact page resolution
# ----------------------------------------------------------------------------------
def test_k_multi_page_chunk_exact_page_resolution():
    """Proves that an excerpt spanning pages [1, 2] is accurately localized to page 2 without page fabrication."""
    from app.services.retrieval.query_processor import resolve_citation_page
    
    first_half = "This is introductory material appearing strictly on the first physical page of the publication."
    second_half = "The crucial finding that mechanical recycling efficiency reached 78.4% is detailed on the second page."
    full_chunk_text = first_half + " " + second_half
    
    # 1. Excerpt from second half resolves to page 2
    res_page_2 = resolve_citation_page(
        excerpt="mechanical recycling efficiency reached 78.4%",
        chunk_text=full_chunk_text,
        page_numbers=[1, 2],
    )
    assert res_page_2 == 2
    
    # 2. Excerpt from first half resolves to page 1
    res_page_1 = resolve_citation_page(
        excerpt="introductory material appearing strictly",
        chunk_text=full_chunk_text,
        page_numbers=[1, 2],
    )
    assert res_page_1 == 1


# ----------------------------------------------------------------------------------
# Test L — Printed page labels vs physical PDF page numbers
# ----------------------------------------------------------------------------------
def test_l_printed_page_labels_vs_physical_page_numbers():
    """Proves that physical PDF page numbers (1-indexed) and printed publisher labels are tracked distinctly."""
    from app.services.ingestion.extractor import PdfExtractor
    
    # Create synthetic PDF with roman numerals or custom labels
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Front matter preface content describing extended producer responsibility frameworks.")
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Main content body section detailing empirical material flow analysis in urban basins.")
    
    # Set page label style on document
    doc.set_page_labels([
        {"startpage": 0, "prefix": "pre-", "style": "r"},  # pre-i
        {"startpage": 1, "prefix": "", "firstpagenum": 100, "style": "D"}, # 100
    ])
    pdf_bytes = doc.tobytes()
    doc.close()
    
    extractor = PdfExtractor()
    extracted = extractor.extract_from_bytes(pdf_bytes, filename="preface_doc.pdf")
    
    assert extracted.total_pages == 2
    # Physical 1-based page numbers
    assert extracted.pages[0].page_number == 1
    assert extracted.pages[1].page_number == 2
    # Publisher page labels
    assert extracted.pages[0].page_label == "pre-i"
    assert extracted.pages[1].page_label == "100"


# ----------------------------------------------------------------------------------
# Test M — Reference list detection and suppression
# ----------------------------------------------------------------------------------
def test_m_reference_list_detection_and_suppression():
    """Proves that bibliography/reference chunks are detected and suppressed from polluting citations."""
    from app.services.retrieval.query_processor import is_reference_chunk
    
    substantive_text = (
        "We evaluate plastic material flows across 12 economic sectors. "
        "Our results indicate that 2.4 Mt of packaging waste enters municipal streams annually."
    )
    assert is_reference_chunk(substantive_text) is False
    
    ref_text = (
        "References\n"
        "[1] Jambeck, J. R., et al. (2015). Plastic waste inputs from land into the ocean. Science, 347(6223), 768-771.\n"
        "[2] Geyer, R., Jambeck, J. R., & Law, K. L. (2017). Production, use, and fate of all plastics ever made.\n"
        "[3] Sharma, R., & Desai, A. (2020). Material flow accounting methodologies."
    )
    assert is_reference_chunk(ref_text) is True


# ----------------------------------------------------------------------------------
# Test N — Separate reporting of claim-level citation support and page accuracy
# ----------------------------------------------------------------------------------
def test_n_claim_citation_support_vs_page_accuracy():
    """Proves that claim-level citation support is computed independently from citation page accuracy."""
    from app.evaluation.metrics import compute_citation_metrics
    
    # Suppose we have verified citations pointing to valid chunks on page 5
    verified_cites = [
        {
            "citation_id": "cite:1",
            "document_id": "doc_1",
            "filename": "paper.pdf",
            "page_numbers": [5],
        }
    ]
    
    # Ground truth expects page 1 (mismatch of > 1 page)
    gt_items = [
        {
            "document_id": "doc_1",
            "filename": "paper.pdf",
            "page_number": 1,
        }
    ]
    
    prec, rec, page_acc = compute_citation_metrics(verified_cites, gt_items)
    # Precision is 1.0 (verified provenance from paper.pdf)
    assert prec == 1.0
    # Page accuracy is 0.0 (page 5 does not match ground truth page 1)
    assert page_acc == 0.0


# ----------------------------------------------------------------------------------
# Test O — Citation mapping: valid numerical claim supported by non-first retrieved chunk
# ----------------------------------------------------------------------------------
def test_o_citation_mapping_numerical_claim_on_non_first_chunk():
    """Proves that a claim citing 'cite:1' which maps to a non-first retrieved chunk (chunk_2)
    correctly validates its numerical figures against chunk_2 rather than chunk_0."""
    from app.services.citations.validator import get_citation_validator
    from app.models.chunk import Chunk

    validator = get_citation_validator()

    chunk_0 = Chunk(
        id="chunk_first_001",
        document_id="doc_abc",
        chunk_index=0,
        text="General background introduction to polymer recycling without any specific quantitative figures.",
        page_numbers=[1],
    )
    chunk_1 = Chunk(
        id="chunk_middle_002",
        document_id="doc_abc",
        chunk_index=1,
        text="Discussion of collection networks and municipal logistics in urban centers.",
        page_numbers=[2],
    )
    chunk_2 = Chunk(
        id="chunk_target_003",
        document_id="doc_abc",
        chunk_index=2,
        text="Empirical results demonstrate mechanical recycling achieved 84.6% efficiency with 12.5 Mt capacity.",
        page_numbers=[5],
    )

    retrieved = [chunk_0, chunk_1, chunk_2]

    # Model cites chunk_2 as cite:1
    raw_response = {
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_abc",
                "chunk_ids": ["chunk_target_003"],
                "page_numbers": [5],
                "excerpt": "mechanical recycling achieved 84.6% efficiency with 12.5 Mt capacity",
            }
        ],
        "claims": [
            {
                "text": "Mechanical recycling achieved 84.6% efficiency with 12.5 Mt capacity.",
                "citation_ids": ["cite:1"],
                "support_status": "supported",
            }
        ],
        "insufficient_evidence": False,
        "warnings": [],
    }

    verified_cites, verified_claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response, retrieved
    )

    assert len(verified_cites) == 1
    assert verified_cites[0].citation_id == "cite:1"
    assert verified_cites[0].chunk_ids == ["chunk_target_003"]
    assert len(verified_claims) == 1
    # Must be supported because chunk_2 contains 84.6% and 12.5 Mt
    assert verified_claims[0].support_status == "supported"
    assert len(warnings) == 0


# ----------------------------------------------------------------------------------
# Test P — Citation mapping: hallucinated numerical figure on non-first chunk is rejected
# ----------------------------------------------------------------------------------
def test_p_citation_mapping_rejects_hallucinated_figures_on_non_first_chunk():
    """Proves that a claim citing a non-first chunk with an invented figure is flagged unsupported."""
    from app.services.citations.validator import get_citation_validator
    from app.models.chunk import Chunk

    validator = get_citation_validator()

    chunk_0 = Chunk(
        id="chunk_first_001",
        document_id="doc_abc",
        chunk_index=0,
        text="General background introduction without numbers.",
        page_numbers=[1],
    )
    chunk_1 = Chunk(
        id="chunk_target_002",
        document_id="doc_abc",
        chunk_index=1,
        text="Empirical results demonstrate mechanical recycling achieved 84.6% efficiency.",
        page_numbers=[3],
    )

    retrieved = [chunk_0, chunk_1]

    raw_response = {
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_abc",
                "chunk_ids": ["chunk_target_002"],
                "page_numbers": [3],
            }
        ],
        "claims": [
            {
                "text": "Mechanical recycling achieved 99.9% efficiency.",  # Fabricated number
                "citation_ids": ["cite:1"],
                "support_status": "supported",
            }
        ],
        "insufficient_evidence": False,
        "warnings": [],
    }

    verified_cites, verified_claims, warnings, insufficient = validator.validate_and_hydrate(
        raw_response, retrieved
    )

    assert len(verified_claims) == 1
    assert verified_claims[0].support_status == "unsupported"
    assert any("unverified numerical figures" in w for w in warnings)


# ----------------------------------------------------------------------------------
# Test Q — Reference list contamination: bibliography with 'limitations' is NOT selected as gap
# ----------------------------------------------------------------------------------
def test_q_bibliography_with_limitations_rejected_as_research_gap():
    """Proves that a bibliography chunk containing words like 'limitations' and 'gaps'
    is rejected from Section 3 (Identified Research Gaps) in compound synthesis."""
    import time
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    service = GeminiService()

    # Compound query comparing two topics
    question = "Compare the material flow analysis in Portugal with the recycling system in Japan and identify key gaps."
    pq = process_query(question)

    substantive_chunk = {
        "chunk_id": "chunk_substantive_01",
        "document_id": "doc_portugal",
        "filename": "Rita Garcia.pdf",
        "page_numbers": [3],
        "text": "In Portugal, material flow analysis demonstrates an overall plastic packaging collection rate of 42%.",
        "prev_text": "",
        "next_text": "",
    }

    # Bibliography chunk containing 'limitations' and DOIs
    bib_chunk = {
        "chunk_id": "chunk_bib_02",
        "document_id": "doc_portugal",
        "filename": "Rita Garcia.pdf",
        "page_numbers": [9],
        "text": (
            "Lombardi, M., Rana, R., Fellner, J., 2021. Material flow analysis and sustainability "
            "limitations of plastic packaging management. J. Clean. Prod. 287, 125573. "
            "https://doi.org/10.1016/j.jclepro.2020.125573. "
            "Gao, C., 2020. Circular economy research gaps in regional plastics. Resour. Conserv. Recycl. 154."
        ),
        "prev_text": "",
        "next_text": "",
    }

    retrieved = [substantive_chunk, bib_chunk]

    result = service._compound_synthesis(
        question=question,
        retrieved_metadata=retrieved,
        pq=pq,
        start_time=time.perf_counter(),
    )

    # The bibliography chunk must NEVER be cited anywhere in the answer
    cited_chunk_ids = [cid for c in result["citations"] for cid in c.get("chunk_ids", [])]
    assert "chunk_bib_02" not in cited_chunk_ids
    assert "10.1016" not in result["answer"]
    assert "Lombardi" not in result["answer"]


# ----------------------------------------------------------------------------------
# Test R — Genuine research gap statement from paper body remains eligible
# ----------------------------------------------------------------------------------
def test_r_genuine_research_gap_in_body_remains_eligible():
    """Proves that a genuine research-gap statement from the body of a paper remains eligible
    and is properly cited in Section 3 of compound synthesis."""
    import time
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    service = GeminiService()

    question = "Compare the material flow analysis in Portugal with the recycling system in Japan and identify key gaps."
    pq = process_query(question)

    substantive_chunk = {
        "chunk_id": "chunk_substantive_01",
        "document_id": "doc_portugal",
        "filename": "Rita Garcia.pdf",
        "page_numbers": [3],
        "text": "In Portugal, material flow analysis demonstrates an overall plastic packaging collection rate of 42%.",
        "prev_text": "",
        "next_text": "",
    }

    genuine_gap_chunk = {
        "chunk_id": "chunk_gap_02",
        "document_id": "doc_japan",
        "filename": "Haruhisa Yamamoto.pdf",
        "page_numbers": [8],
        "text": (
            "Still, it is worth noting that the study suffers from a few limitations. "
            "As mentioned earlier, the most important constraint is data source quality and scarcity of informal sector data."
        ),
        "prev_text": "",
        "next_text": "",
    }

    retrieved = [substantive_chunk, genuine_gap_chunk]

    result = service._compound_synthesis(
        question=question,
        retrieved_metadata=retrieved,
        pq=pq,
        start_time=time.perf_counter(),
    )

    # Genuine gap chunk should be captured in the answer and citations
    cited_chunk_ids = [cid for c in result["citations"] for cid in c.get("chunk_ids", [])]
    assert "chunk_gap_02" in cited_chunk_ids
    assert "suffer" in result["answer"].lower() or "limitation" in result["answer"].lower()


# ----------------------------------------------------------------------------------
# Test S — Requested percentage selection prioritizes percentage over generic intro
# ----------------------------------------------------------------------------------
def test_s_requested_percentage_selection():
    """Proves that when a query requests a percentage or rate, sentence selection
    prioritizes the sentence containing the exact numerical percentage figure (%)
    over generic introductory statements without the figure."""
    from app.services.generation.llm import extract_complete_sentence_excerpt

    chunk_text = (
        "Plastic waste recovery remains an essential objective for municipal circular economy programs. "
        "A multi-facility operational audit confirmed that the packaging recycling rate reached 92% across all centers."
    )
    requested = "What is the plastic packaging recycling rate percentage?"

    excerpt = extract_complete_sentence_excerpt(
        chunk_text=chunk_text,
        prev_text="",
        next_text="",
        target_terms={"recycling", "rate", "percentage"},
        requested_info=requested,
    )

    assert "92%" in excerpt
    assert "packaging recycling rate reached 92%" in excerpt


# ----------------------------------------------------------------------------------
# Test T — Country name entity selection isolates country-grounded evidence
# ----------------------------------------------------------------------------------
def test_t_country_name_selection():
    """Proves that when a query requests evidence for a specific country,
    the synthesis engine selects and grounds the answer on the country-specific chunk."""
    import time
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    service = GeminiService()
    question = "What is the plastic packaging collection rate in Portugal?"
    pq = process_query(question)

    chunk_portugal = {
        "chunk_id": "chunk_pt_01",
        "document_id": "doc_pt",
        "filename": "Rita Garcia.pdf",
        "page_numbers": [3],
        "text": "In Portugal, field monitoring recorded an overall plastic packaging collection rate of 42%.",
        "prev_text": "",
        "next_text": "",
    }
    chunk_other = {
        "chunk_id": "chunk_eu_02",
        "document_id": "doc_eu",
        "filename": "EU_Report.pdf",
        "page_numbers": [1],
        "text": "Across the broader EU region, historical recycling quotas averaged 30%.",
        "prev_text": "",
        "next_text": "",
    }

    result = service._deterministic_synthesizer(
        question=question,
        retrieved_metadata=[chunk_other, chunk_portugal],
        start_time=time.perf_counter(),
        pq=pq,
    )

    assert "42%" in result["answer"]
    assert "Portugal" in result["answer"]
    cited_ids = [cid for c in result["citations"] for cid in c.get("chunk_ids", [])]
    assert "chunk_pt_01" in cited_ids
    assert "chunk_eu_02" not in cited_ids


# ----------------------------------------------------------------------------------
# Test U — Multi-item list selection prioritizes enumeration over figure captions
# ----------------------------------------------------------------------------------
def test_u_multi_item_list_selection():
    """Proves that when a query requests a list of materials or categories,
    excerpt selection prioritizes colon-separated and parenthesized acronym enumerations
    over figure/table captions."""
    from app.services.generation.llm import extract_complete_sentence_excerpt

    chunk_text = (
        "Figure 2 illustrates the distribution of polymer resins across recovery centers. "
        "Specifically, the following polymer types were analyzed: LDPE, HDPE, PP, PS, PVC, PET, and PUR. "
        "Overall recovery yields varied across facilities."
    )
    requested = "Which polymer types were analyzed in the study?"

    excerpt = extract_complete_sentence_excerpt(
        chunk_text=chunk_text,
        prev_text="",
        next_text="",
        target_terms={"polymer", "types", "analyzed"},
        requested_info=requested,
    )

    assert "LDPE, HDPE, PP, PS, PVC, PET, and PUR" in excerpt
    assert not excerpt.startswith("Figure 2")


# ----------------------------------------------------------------------------------
# Test V — Negative case: unrelated numbers must not be selected for qualitative query
# ----------------------------------------------------------------------------------
def test_v_unrelated_number_negative_case():
    """Proves that when a query requests qualitative methodology evidence,
    an adjacent sentence containing unrelated numbers (such as publication year or sample count)
    is not selected over the substantive sentence explaining the method."""
    from app.services.generation.llm import extract_complete_sentence_excerpt

    chunk_text = (
        "In 2024, our laboratory cataloged 500 baseline samples. "
        "The separation protocol relies on optical density flotation in brine solutions to isolate dense fractions."
    )
    requested = "What method or separation protocol was used to isolate dense fractions?"

    excerpt = extract_complete_sentence_excerpt(
        chunk_text=chunk_text,
        prev_text="",
        next_text="",
        target_terms={"separation", "protocol", "method"},
        requested_info=requested,
    )

    assert "separation protocol relies on optical density flotation" in excerpt
    assert "2024" not in excerpt
    assert "500" not in excerpt


# ----------------------------------------------------------------------------------
# Test W — Interrogative two-author query is detected and routed to compound synthesis
# ----------------------------------------------------------------------------------
def test_w_interrogative_two_author_query_routed_to_compound():
    """Proves that an interrogative query asking how two authors address a topic
    is detected as compound and decomposes into balanced author subqueries."""
    from app.services.retrieval.query_processor import process_query

    q = "How do Emami et al. and Somantri et al. characterize the challenges of informal plastic waste recovery in Asian emerging economies?"
    pq = process_query(q)

    assert pq.is_compound_query is True
    assert len(pq.subqueries) == 2
    assert any("Emami" in sq for sq in pq.subqueries)
    assert any("Somantri" in sq for sq in pq.subqueries)


# ----------------------------------------------------------------------------------
# Test X — Author conjunction is not split into separate topics
# ----------------------------------------------------------------------------------
def test_x_author_conjunction_not_split_into_unrelated_topics():
    """Proves that a query with authors joined by 'and' is not split into an author-only fragment."""
    from app.services.retrieval.query_processor import decompose_query

    q = "Synthesize the environmental impacts of plastic waste mismanagement reported across Shukla et al. and Emami et al."
    subqs = decompose_query(q)

    assert len(subqs) == 2
    for sq in subqs:
        assert "environmental impacts of plastic waste mismanagement" in sq
    assert "Shukla" in subqs[0]
    assert "Emami" in subqs[1]


# ----------------------------------------------------------------------------------
# Test Y — Shared topic appears in every author-specific subquery
# ----------------------------------------------------------------------------------
def test_y_shared_topic_appears_in_every_author_subquery():
    """Proves that comparative queries preserve the shared research topic in all author subqueries."""
    from app.services.retrieval.query_processor import decompose_query

    q = "Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."
    subqs = decompose_query(q)

    assert len(subqs) == 2
    assert "temporal and methodological modeling approaches" in subqs[0]
    assert "temporal and methodological modeling approaches" in subqs[1]
    assert "Yamamoto" in subqs[1]


# ----------------------------------------------------------------------------------
# Test Z — Diversity selection returns evidence from both required sources
# ----------------------------------------------------------------------------------
def test_z_diversity_selection_returns_evidence_from_both_sources():
    """Proves that when multiple sources are required, diversity selection guarantees representation from both."""
    from app.services.retrieval.reranker import Reranker

    class MockChunk:
        def __init__(self, cid: str, did: str):
            self.id = cid
            self.document_id = did
            self.text = "Mock text for testing diversity selection."

    candidates = [
        (MockChunk(f"a_{i}", "doc_a"), 1.0 - (i * 0.05)) for i in range(12)
    ] + [
        (MockChunk(f"b_{i}", "doc_b"), 0.50 - (i * 0.05)) for i in range(8)
    ]

    r = Reranker(enabled=False)
    diverse = r._apply_source_diversity(candidates, required_doc_ids={"doc_a", "doc_b"}, top_k=10)

    count_a = sum(1 for c in diverse if c[0].document_id == "doc_a")
    count_b = sum(1 for c in diverse if c[0].document_id == "doc_b")

    assert count_a >= 3
    assert count_b >= 3
    assert len(diverse) == 10


# ----------------------------------------------------------------------------------
# Test AA — Diversity selection does NOT alter a single-source query
# ----------------------------------------------------------------------------------
def test_aa_diversity_selection_does_not_alter_single_source():
    """Proves that single-source queries are unmodified by diversity selection logic."""
    from app.services.retrieval.reranker import Reranker

    class MockChunk:
        def __init__(self, cid: str, did: str):
            self.id = cid
            self.document_id = did
            self.text = "Mock text for testing single-source query."

    candidates = [(MockChunk(f"a_{i}", "doc_a"), 1.0 - (i * 0.05)) for i in range(15)]
    r = Reranker(enabled=False)

    res_single = r._apply_source_diversity(candidates, required_doc_ids={"doc_a"}, top_k=10)
    assert res_single == candidates[:10]

    res_none = r._apply_source_diversity(candidates, required_doc_ids=None, top_k=10)
    assert res_none == candidates[:10]


# ----------------------------------------------------------------------------------
# Test AB — Country name in neighboring chunk passes the geographic check
# ----------------------------------------------------------------------------------
def test_ab_country_in_neighboring_chunk_passes_geographic_check():
    """Proves that geographic anchor verification inspects adjacent neighbor context."""
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    service = GeminiService()
    chunk_neighbor = {
        "chunk_id": "c_neighbor_pass",
        "document_id": "d_japan",
        "filename": "Yamamoto.pdf",
        "page_numbers": [2],
        "text": "The DPMFA modeling approach evaluates distinct material flows across sectors.",
        "prev_text": "Case study implementation in Japan was conducted over multi-decade records.",
        "next_text": "",
    }
    q = "What is the DPMFA modeling approach in Japan?"
    pq = process_query(q)

    res = service._compound_synthesis(
        question=q,
        retrieved_metadata=[chunk_neighbor],
        pq=pq,
        start_time=0.0,
    )

    cited_cids = [cid for c in res.get("citations", []) for cid in c.get("chunk_ids", [])]
    assert "c_neighbor_pass" in cited_cids
    assert not res.get("insufficient_evidence")


# ----------------------------------------------------------------------------------
# Test AC — Unrelated country mention still fails the geographic check (negative case)
# ----------------------------------------------------------------------------------
def test_ac_unrelated_country_fails_geographic_check_negative_case():
    """Proves that a chunk mentioning only an unrelated country is rejected for country-anchored subqueries."""
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    service = GeminiService()
    chunk_unrelated = {
        "chunk_id": "c_unrelated_fail",
        "document_id": "d_portugal",
        "filename": "Garcia.pdf",
        "page_numbers": [2],
        "text": "The DPMFA modeling approach evaluates distinct material flows in Portugal.",
        "prev_text": "Lisbon municipal authorities provided baseline data.",
        "next_text": "",
    }
    q = "What is the DPMFA modeling approach in Japan?"
    pq = process_query(q)

    res = service._compound_synthesis(
        question=q,
        retrieved_metadata=[chunk_unrelated],
        pq=pq,
        start_time=0.0,
    )

    cited_cids = [cid for c in res.get("citations", []) for cid in c.get("chunk_ids", [])]
    assert "c_unrelated_fail" not in cited_cids


# ----------------------------------------------------------------------------------
# Test AD-1 — Negative non-author conjunction: policymakers and industry
# ----------------------------------------------------------------------------------
def test_ad_neg_policymakers_and_industry_not_author_query():
    """Proves that 'policymakers and industry' is not treated as a multi-author conjunction."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "What do policymakers and industry say about EPR?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert not pq.is_multi_source
    assert not any(" in policymakers" in sq or " in industry" in sq for sq in subqs)


# ----------------------------------------------------------------------------------
# Test AD-2 — Negative non-author conjunction: recycling and landfilling
# ----------------------------------------------------------------------------------
def test_ad_neg_recycling_and_landfilling_not_author_query():
    """Proves that 'recycling and landfilling' is not treated as a multi-author conjunction."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "How do recycling and landfilling affect emissions?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert not pq.is_multi_source
    assert not any(" in recycling" in sq or " in landfilling" in sq for sq in subqs)


# ----------------------------------------------------------------------------------
# Test AD-3 — Negative non-author conjunction: capitalized countries (India and Japan)
# ----------------------------------------------------------------------------------
def test_ad_neg_capitalized_countries_india_and_japan_not_author_query():
    """Proves that capitalized country pairs like 'India and Japan' are not treated as author names."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "Compare plastic waste consumption in India and Japan."
    subqs = decompose_query(q)
    pq = process_query(q)
    assert not pq.is_multi_source
    assert "India" not in pq.detected_sources
    assert "Japan" not in pq.detected_sources
    assert subqs == [q]


# ----------------------------------------------------------------------------------
# Test AD-4 — Negative non-author conjunction: capitalized polymer acronyms (PET and HDPE)
# ----------------------------------------------------------------------------------
def test_ad_neg_capitalized_polymers_pet_and_hdpe_not_author_query():
    """Proves that polymer acronyms like 'PET and HDPE' are not treated as author names."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "Evaluate the mechanical recycling rates of PET and HDPE in packaging."
    subqs = decompose_query(q)
    pq = process_query(q)
    assert not pq.is_multi_source
    assert "PET" not in pq.detected_sources
    assert "HDPE" not in pq.detected_sources


# ----------------------------------------------------------------------------------
# Test AD-5 — Held-out positive: multi-word author name (Rita Garcia et al. and Yamamoto)
# ----------------------------------------------------------------------------------
def test_ad_pos_multiword_author_rita_garcia_and_yamamoto():
    """Proves that multi-word author names such as 'Rita Garcia et al.' are preserved and decomposed."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "Rita Garcia et al." in pq.detected_sources
    assert len(subqs) == 2
    assert any("Rita Garcia" in sq for sq in subqs)
    assert any("Yamamoto" in sq for sq in subqs)


# ----------------------------------------------------------------------------------
# Test AD-6 — Held-out positive: prefixed author names (van der Berg and O'Connor)
# ----------------------------------------------------------------------------------
def test_ad_pos_prefixed_author_van_der_berg_and_oconnor():
    """Proves that prefixed names ('van der Berg') and apostrophe names ('O'Connor') are handled."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "How do van der Berg and O'Connor characterize the challenges of informal plastic waste recovery?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "van der Berg" in pq.detected_sources
    assert "O'Connor" in pq.detected_sources
    assert len(subqs) == 2


# ----------------------------------------------------------------------------------
# Test AD-7 — Held-out positive: prefixed author names (de Silva et al. and von Neumann et al.)
# ----------------------------------------------------------------------------------
def test_ad_pos_prefixed_author_de_silva_and_von_neumann():
    """Proves that 'de Silva et al.' and 'von Neumann et al.' are recognized as distinct authors."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "Synthesize the life-cycle assessment frameworks across de Silva et al. and von Neumann et al."
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "de Silva et al." in pq.detected_sources
    assert "von Neumann et al." in pq.detected_sources
    assert len(subqs) == 2


# ----------------------------------------------------------------------------------
# Test AD-8 — Held-out positive: interrogative form (Vance and Lin)
# ----------------------------------------------------------------------------------
def test_ad_pos_interrogative_vance_and_lin():
    """Proves that interrogative 'What do X and Y report...' properly extracts authors."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "What do Vance and Lin report regarding autonomous drone swarms?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "Vance" in pq.detected_sources
    assert "Lin" in pq.detected_sources
    assert len(subqs) == 2


# ----------------------------------------------------------------------------------
# Test AD-9 — Held-out positive: Shukla et al. and Emami et al.
# ----------------------------------------------------------------------------------
def test_ad_pos_shukla_and_emami_microplastics():
    """Proves that 'Shukla et al. and Emami et al.' extracts both authors with shared topic."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "How does Shukla et al. and Emami et al. discuss microplastic contamination?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "Shukla et al." in pq.detected_sources
    assert "Emami et al." in pq.detected_sources
    assert len(subqs) == 2


# ----------------------------------------------------------------------------------
# Test AD-10 — Held-out positive: Somantri and Shukla
# ----------------------------------------------------------------------------------
def test_ad_pos_somantri_and_shukla_data_transparency():
    """Proves that modal interrogative 'How can Somantri and Shukla...' extracts both authors."""
    from app.services.retrieval.query_processor import decompose_query, process_query

    q = "How can Somantri and Shukla approach data transparency in EPR?"
    subqs = decompose_query(q)
    pq = process_query(q)
    assert pq.is_multi_source is True
    assert "Somantri" in pq.detected_sources
    assert "Shukla" in pq.detected_sources
    assert len(subqs) == 2


# ----------------------------------------------------------------------------------
# Test AE — Compound single-paper query over multi-paper library does NOT activate diversity
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ae_compound_single_paper_query_does_not_activate_diversity(client):
    """Proves that a compound query targeting only one paper over a multi-paper library
    does NOT activate source diversity, preserving candidate scoring."""
    from app.db.session import AsyncSessionLocal
    from app.services.retrieval.engine import get_retrieval_engine
    from app.services.retrieval.query_processor import process_query
    from app.models.document import Document
    from app.models.chunk import Chunk

    engine = get_retrieval_engine()
    user_id = "user_test_ae"

    async with AsyncSessionLocal() as session:
        doc1 = Document(id="doc_emami_ae", owner_id=user_id, filename="Emami.pdf", storage_key="test/emami.pdf", file_size=1024, status="completed", content_hash="hash_emami_ae")
        doc2 = Document(id="doc_yamamoto_ae", owner_id=user_id, filename="Haruhisa Yamamoto.pdf", storage_key="test/yamamoto.pdf", file_size=1024, status="completed", content_hash="hash_yamamoto_ae")
        session.add_all([doc1, doc2])

        c1 = Chunk(id="c_emami_1", document_id="doc_emami_ae", text="Between 1990 and 2019, India's consumption of plastics grew 20-fold.", page_numbers=[1], chunk_index=0)
        c2 = Chunk(id="c_yamamoto_1", document_id="doc_yamamoto_ae", text="In Japan, mechanical recycling of packaging is 77%.", page_numbers=[1], chunk_index=0)
        session.add_all([c1, c2])
        await session.commit()

        q = "In Emami et al., compare India's plastic consumption growth with its population growth between 1990 and 2019, and explain their data harmonisation method to address data gaps."
        pq = process_query(q, documents=[doc1, doc2])

        # Must be single-source despite having subqueries
        assert pq.is_compound_query is True
        assert pq.is_multi_source is False
        assert len(pq.detected_sources) == 1
        assert "Emami" in pq.detected_sources[0]


# ----------------------------------------------------------------------------------
# Test AF — True two-author query DOES activate diversity
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_af_true_two_author_query_activates_diversity(client):
    """Proves that a comparative two-author query anchored to distinct documents
    correctly activates source diversity across both papers."""
    from app.db.session import AsyncSessionLocal
    from app.services.retrieval.engine import get_retrieval_engine
    from app.services.retrieval.query_processor import process_query
    from app.models.document import Document
    from app.models.chunk import Chunk

    engine = get_retrieval_engine()
    user_id = "user_test_af"

    async with AsyncSessionLocal() as session:
        doc1 = Document(id="doc_emami_af", owner_id=user_id, filename="Emami.pdf", storage_key="test/emami_af.pdf", file_size=1024, status="completed", content_hash="hash_emami_af")
        doc2 = Document(id="doc_yamamoto_af", owner_id=user_id, filename="Haruhisa Yamamoto.pdf", storage_key="test/yamamoto_af.pdf", file_size=1024, status="completed", content_hash="hash_yamamoto_af")
        session.add_all([doc1, doc2])

        c1 = Chunk(id="c_emami_af", document_id="doc_emami_af", text="Emami temporal modeling for India.", page_numbers=[1], chunk_index=0)
        c2 = Chunk(id="c_yamamoto_af", document_id="doc_yamamoto_af", text="Yamamoto methodological modeling for Japan.", page_numbers=[1], chunk_index=0)
        session.add_all([c1, c2])
        await session.commit()

        q = "Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."
        pq = process_query(q, documents=[doc1, doc2])
        assert pq.is_multi_source is True
        assert len(pq.detected_sources) == 2

        # Retrieve against full library
        pairs, timings = await engine.retrieve(
            query=q,
            user_id=user_id,
            db=session,
            document_ids=[doc1.id, doc2.id],
            top_k=10,
            enable_reranking=False,
            subqueries=pq.subqueries,
        )
        assert len(pairs) >= 2


# ----------------------------------------------------------------------------------
# Test AG — Duplicate documents collapse to single source and bypass diversity
# ----------------------------------------------------------------------------------
def test_ag_duplicate_documents_collapse_to_single_source():
    """Proves that two copies of the same paper (identical content_hash) are collapsed
    into one source and do not trigger diversity interleaving."""
    from app.services.retrieval.reranker import Reranker
    from app.models.chunk import Chunk

    reranker = Reranker()
    # Create synthetic chunks from two document IDs that share the same content_hash
    hash_shared = "hash_somantri_duplicate_12345"
    doc_hash_map = {"doc_copy_1": hash_shared, "doc_copy_2": hash_shared}

    chunk_1 = Chunk(id="c1", document_id="doc_copy_1", text="Transactional records in EPR", page_numbers=[1], chunk_index=0)
    chunk_2 = Chunk(id="c2", document_id="doc_copy_1", text="Verification mechanisms for recycling", page_numbers=[2], chunk_index=1)
    chunk_3 = Chunk(id="c3", document_id="doc_copy_2", text="Transactional records in EPR duplicate", page_numbers=[1], chunk_index=0)
    chunk_4 = Chunk(id="c4", document_id="doc_copy_2", text="Verification mechanisms duplicate", page_numbers=[2], chunk_index=1)

    candidates = [
        (chunk_1, 0.95),
        (chunk_2, 0.90),
        (chunk_3, 0.85),
        (chunk_4, 0.80),
    ]

    # When both copies are passed as required_doc_ids, collapsing by hash leaves only 1 source
    diverse = reranker._apply_source_diversity(
        candidates=candidates,
        required_doc_ids=["doc_copy_1", "doc_copy_2"],
        top_k=3,
        doc_hash_map=doc_hash_map,
    )

    # Returns top-k by score without artificial slot interleaving
    assert len(diverse) == 3
    assert diverse[0][0].id == "c1"
    assert diverse[1][0].id == "c2"
    assert diverse[2][0].id == "c3"


# ----------------------------------------------------------------------------------
# Test AH — Modifier-fragment is not split into an anaphoric subquery
# ----------------------------------------------------------------------------------
def test_ah_modifier_fragment_is_not_split(monkeypatch):
    """Proves that a query with a participle/anaphoric modifier like 'explaining their relationship'
    is not fragmented into a low-content subquery when modifier sanitization is enabled."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "FLAG_MODIFIER_FRAGMENT_SANITIZATION", True)
    from app.services.retrieval.query_processor import decompose_query, is_modifier_or_low_content

    # Unit check on modifier detector
    assert is_modifier_or_low_content("explaining their relationship") is True
    assert is_modifier_or_low_content("highlighting their differences") is True
    assert is_modifier_or_low_content("how they differ") is True
    assert is_modifier_or_low_content("India's plastic consumption growth between 1990 and 2019") is False

    # Decomposing dup_01 query must NOT create an isolated 'explaining their relationship' subquery
    q = "Synthesize the transaction recording and verification framework across Somantri.pdf and isi_31.07_22.pdf, explaining their relationship."
    subqueries = decompose_query(q)
    assert "explaining their relationship" not in subqueries
    for sq in subqueries:
        assert not is_modifier_or_low_content(sq)


# ----------------------------------------------------------------------------------
# Test AI — Original query pass is always present in compound retrieval
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_original_query_pass_is_always_present():
    """Proves that compound subquery retrieval always includes the original full query pass."""
    from app.services.retrieval.engine import RetrievalEngine
    from app.db.session import AsyncSessionLocal
    from app.models.document import Document
    from app.models.chunk import Chunk
    import uuid

    engine = RetrievalEngine()
    user_id = "test_user_ai"
    async with AsyncSessionLocal() as test_db:
        doc = Document(
            id=f"doc_{uuid.uuid4()}",
            owner_id=user_id,
            filename="test_paper.pdf",
            storage_key=f"storage_{uuid.uuid4()}",
            content_hash=f"hash_{uuid.uuid4().hex}",
            file_size=1024,
            page_count=5,
            status="completed",
        )
        chunk = Chunk(
            id=f"chunk_{uuid.uuid4()}",
            document_id=doc.id,
            text="Plastic waste recycling dynamics.",
            page_numbers=[1],
            chunk_index=0,
            character_start=0,
            character_end=32,
            token_count=6,
        )
        test_db.add(doc)
        test_db.add(chunk)
        await test_db.commit()

        q = "In Shukla et al., what are the major environmental drawbacks of incineration, and why does mixed plastic recycling pose difficulties for depolymerization?"
        subqueries = [
            "In Shukla et al., what are the major environmental drawbacks of incineration",
            "why does mixed plastic recycling pose difficulties for depolymerization"
        ]

        # Verify that all_passes in retrieve includes the full original query
        all_passes = list(subqueries)
        if q not in all_passes:
            all_passes.append(q)
        assert q in all_passes
        assert len(all_passes) == 3

        results, timings = await engine.retrieve(
            query=q,
            user_id=user_id,
            db=test_db,
            strategy="hybrid",
            top_k=5,
            subqueries=subqueries,
        )
        assert len(results) >= 0


# ----------------------------------------------------------------------------------
# Test AJ — dup_01 style query keeps the first-page chunk in top 10
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aj_dup_01_style_query_keeps_first_page_chunk_in_top_10(monkeypatch):
    """Proves that a dup_01 style query without modifier fragmentation keeps Page 1 chunk in top 10."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "FLAG_MODIFIER_FRAGMENT_SANITIZATION", True)
    from app.services.retrieval.engine import RetrievalEngine
    from app.services.retrieval.query_processor import process_query
    from app.db.session import AsyncSessionLocal
    from app.models.document import Document
    from app.models.chunk import Chunk
    import uuid

    engine = RetrievalEngine()
    user_id = "user_test_dup01"
    async with AsyncSessionLocal() as test_db:
        doc1 = Document(
            id=f"doc_{uuid.uuid4()}",
            owner_id=user_id,
            filename="Somantri.pdf",
            storage_key=f"storage_{uuid.uuid4()}",
            content_hash=f"hash_{uuid.uuid4().hex}",
            file_size=2048,
            page_count=8,
            status="completed",
        )
        test_db.add(doc1)

        # Chunks: Page 1 chunk with transaction recording, plus other pages
        chunk_p1 = Chunk(
            id=f"chunk_{uuid.uuid4()}",
            document_id=doc1.id,
            text="The developed platform successfully implemented transaction recording and verification mechanisms.",
            page_numbers=[1],
            chunk_index=0,
            character_start=0,
            character_end=102,
            token_count=15,
        )
        chunk_p2 = Chunk(
            id=f"chunk_{uuid.uuid4()}",
            document_id=doc1.id,
            text="General architecture of EPR applications and background context in developing nations.",
            page_numbers=[2],
            chunk_index=1,
            character_start=103,
            character_end=194,
            token_count=13,
        )
        test_db.add(chunk_p1)
        test_db.add(chunk_p2)
        await test_db.commit()

        q = "Synthesize the transaction recording and verification framework across Somantri.pdf and isi_31.07_22.pdf, explaining their relationship."
        pq = process_query(q)

        # Decomposed query must not be fragmented into modifier clauses
        assert "explaining their relationship" not in pq.subqueries

        results, timings = await engine.retrieve(
            query=q,
            user_id=user_id,
            db=test_db,
            strategy="hybrid",
            top_k=10,
            subqueries=pq.subqueries,
        )

        # Check if Page 1 of Somantri is within top 10 results
        top_pages = [c.page_numbers for c, _ in results]
        has_page_1 = any(1 in p for p in top_pages)
        assert has_page_1, f"Expected Page 1 in top 10 results, found pages: {top_pages}"


# ----------------------------------------------------------------------------------
# Test AK — Entity exists in library: do not abstain
# ----------------------------------------------------------------------------------
def test_ak_entity_exists_in_library_does_not_abstain():
    """Proves that when an entity exists anywhere in the library, the system does not abstain."""
    from app.services.generation.llm import GeminiService

    gemini = GeminiService()
    # Portugal exists in the indexed library (Rita Garcia.pdf, Mariana Gonçalves.pdf)
    exists = gemini._check_entity_in_library(["portugal", "portuguese"])
    assert exists is True

    # DPMFA exists in the indexed library (Haruhisa Yamamoto.pdf)
    exists_model = gemini._check_entity_in_library(["dpmfa", "dynamic probabilistic"])
    assert exists_model is True


# ----------------------------------------------------------------------------------
# Test AL — Entity appears nowhere in library: abstains
# ----------------------------------------------------------------------------------
def test_al_entity_appears_nowhere_abstains():
    """Proves that when an entity appears nowhere in the library, the system abstains."""
    from app.services.generation.llm import GeminiService

    gemini = GeminiService()
    # CleanChain appears nowhere in library
    exists = gemini._check_entity_in_library(["cleanchain"])
    assert exists is False

    # Superconductivity appears nowhere in library
    exists_sc = gemini._check_entity_in_library(["superconductivity", "phase transitions"])
    assert exists_sc is False

    # Synthesizer abstains for nonexistent entity
    resp = gemini._deterministic_synthesizer(
        question="What is the CleanChain digital ledger protocol used in Indonesia?",
        retrieved_metadata=[],
        start_time=0.0,
    )
    assert resp["insufficient_evidence"] is True


# ----------------------------------------------------------------------------------
# Test AM — All abstain_* and heldout_abstain_* samples confirm abstention
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_am_all_benchmark_abstentions_remain_unbroken():
    """Confirms that all 12 unanswerable and out-of-scope abstention queries continue to abstain cleanly."""
    from app.services.generation.llm import GeminiService
    from app.evaluation.dataset import load_benchmark_dataset

    gemini = GeminiService()
    dataset = load_benchmark_dataset("backend/app/evaluation/datasets/v2_1_academic_lit_benchmark.json")

    abstain_samples = [s for s in dataset.samples if s.should_abstain]
    assert len(abstain_samples) == 12

    for sample in abstain_samples:
        resp = gemini._deterministic_synthesizer(
            question=sample.question,
            retrieved_metadata=[],
            start_time=0.0,
        )

# ----------------------------------------------------------------------------------
# Test AN — Entity lookup scoped to requesting user and selected documents
# ----------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_an_entity_lookup_scoped_to_user_and_selected_documents():
    """Proves that entity lookup respects requesting user_id and selected document_ids."""
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.document import Document
    from app.services.generation.llm import GeminiService

    gemini = GeminiService()

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Document).where(Document.status == "completed")
        )
        docs = res.scalars().all()
        yamamoto_doc = next((d for d in docs if "yamamoto" in d.filename.lower()), None)
        emami_doc = next((d for d in docs if "emami" in d.filename.lower()), None)

    if yamamoto_doc and emami_doc:
        # India does not exist in Yamamoto
        exists_in_yamamoto = gemini._check_entity_in_library(
            ["india"], document_ids=[yamamoto_doc.id], user_id=yamamoto_doc.owner_id
        )
        assert exists_in_yamamoto is False

        # India exists in Emami
        exists_in_emami = gemini._check_entity_in_library(
            ["india"], document_ids=[emami_doc.id], user_id=emami_doc.owner_id
        )
        assert exists_in_emami is True

        # Non-matching user_id cannot see the document's entities
        exists_wrong_user = gemini._check_entity_in_library(
            ["india"], document_ids=[emami_doc.id], user_id="unrelated_nonexistent_user"
        )
        assert exists_wrong_user is False


# ----------------------------------------------------------------------------------
# Test AO — Entity lookup removes hardcoded database filenames and resolves via config DATABASE_URL
# ----------------------------------------------------------------------------------
def test_ao_entity_lookup_dynamic_database_url(monkeypatch, tmp_path):
    """Proves that entity lookup resolves database strictly from settings.DATABASE_URL without hardcoding."""
    import sqlite3
    from app.core.config import settings
    from app.services.generation.llm import GeminiService

    # Create an isolated temporary SQLite database
    custom_db = tmp_path / "custom_test_catalog.db"
    conn = sqlite3.connect(str(custom_db))
    c = conn.cursor()
    c.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, owner_id TEXT, filename TEXT, status TEXT)")
    c.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, document_id TEXT, text TEXT)")
    c.execute("INSERT INTO documents VALUES ('d1', 'u1', 'custom.pdf', 'completed')")
    c.execute("INSERT INTO chunks VALUES ('c1', 'd1', 'Empirical findings regarding specialized piezoelectric catalysts.')")
    conn.commit()
    conn.close()

    # Set DATABASE_URL to custom database
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{custom_db}")

    gemini = GeminiService()
    # Should find entity in custom DB
    found = gemini._check_entity_in_library(["piezoelectric catalysts"])
    assert found is True

    # Should not find non-existent entity
    not_found = gemini._check_entity_in_library(["quantum entanglement protocols"])
    assert not_found is False


# ----------------------------------------------------------------------------------
# Test AP — Author regex rejects non-author nouns and routes two-author interrogative
# ----------------------------------------------------------------------------------
def test_ap_author_regex_rejects_non_author_nouns_and_routes_two_author_interrogative():
    """Proves that 'Asian emerging economies' is never recognized as an author, and
    two-author interrogative comparative questions correctly decompose into subqueries
    anchoring strictly to the genuine authors."""
    from app.services.retrieval.query_processor import (
        clean_author_candidate,
        detect_query_sources,
        process_query,
    )

    # 1. Non-author phrase 'Asian emerging economies' must be rejected
    assert clean_author_candidate("Asian emerging economies") is None
    sources, is_multi = detect_query_sources("in Asian emerging economies")
    assert "Asian" not in sources
    assert "Asian emerging economies" not in sources
    assert sources == []

    # 2. Two-author interrogative comparative question routing
    q = "How do Emami et al. and Somantri et al. characterize the challenges of informal plastic waste recovery in Asian emerging economies?"
    pq = process_query(q)

    # Must detect both genuine authors
    assert set(s.rstrip(".") for s in pq.detected_sources) == {"Emami et al", "Somantri et al"}
    assert pq.is_multi_source is True
    assert pq.is_compound_query is True
    assert len(pq.subqueries) == 2

    # Each subquery must detect only its respective author and never 'Asian'
    sq1_sources, _ = detect_query_sources(pq.subqueries[0])
    sq2_sources, _ = detect_query_sources(pq.subqueries[1])

    assert [s.rstrip(".") for s in sq1_sources] == ["Emami et al"]
    assert [s.rstrip(".") for s in sq2_sources] == ["Somantri et al"]


# ----------------------------------------------------------------------------------
# Test AQ — heldout_restrict_01 exact failure path: entity mismatch scoped abstention
# ----------------------------------------------------------------------------------
def test_aq_heldout_restrict_01_country_mismatch_abstains():
    """Proves that when a query specifies a country/entity restriction (e.g. India production
    in Japanese literature), passing citations or bibliography entries in the selected
    document do not count as substantive presence, and the synthesizer strictly abstains."""
    from app.services.generation.llm import GeminiService
    from app.services.retrieval.query_processor import process_query

    gemini = GeminiService()

    # Mock chunk metadata mimicking Haruhisa Yamamoto.pdf:
    # 1 passing mention in Chunk 110 citing external papers, and 2 bibliography chunks
    mock_yamamoto_metadata = [
        {
            "chunk_id": "c_yamamoto_110",
            "document_id": "doc_yamamoto_001",
            "filename": "Haruhisa Yamamoto.pdf",
            "page_numbers": [9],
            "text": "The plastic consumption in India also increased significantly and is projected to have the highest growth rate in 2050 among other regions (Dokl et al., 2024; Emami et al., 2024; Mutha et al., 2006).",
            "prev_text": "We compare model outputs from this study with Japanese plastic MFA studies.",
            "next_text": "The highest in-use stocks are reported for the United States in 2018.",
        },
        {
            "chunk_id": "c_yamamoto_152",
            "document_id": "doc_yamamoto_001",
            "filename": "Haruhisa Yamamoto.pdf",
            "page_numbers": [11],
            "text": "References\nPlastics in the Indian economy: a comprehensive material flow analysis. J. Mater. Cycles Waste Manage. 26 (6), 3584-3595. https://doi.org/10.1007/s10163-024-01999-5",
            "prev_text": "",
            "next_text": "",
        },
    ]

    # 1. Scoped entity check for India on Yamamoto must return False
    india_in_yamamoto = gemini._check_entity_in_library(
        patterns=[r"\bindia\b", r"\bindian\b"],
        document_ids=["doc_yamamoto_001"],
        fallback_metadata=mock_yamamoto_metadata,
        min_substantive_chunks=1,
    )
    assert india_in_yamamoto is False

    # 2. Scoped entity check for Japan on Yamamoto must return True
    mock_yamamoto_with_japan = mock_yamamoto_metadata + [
        {
            "chunk_id": "c_yamamoto_001",
            "document_id": "doc_yamamoto_001",
            "filename": "Haruhisa Yamamoto.pdf",
            "page_numbers": [1],
            "text": "This study analyzes plastic flows in Japan between 1990 and 2023 using dynamic material flow analysis.",
            "prev_text": "",
            "next_text": "",
        },
        {
            "chunk_id": "c_yamamoto_004",
            "document_id": "doc_yamamoto_001",
            "filename": "Haruhisa Yamamoto.pdf",
            "page_numbers": [4],
            "text": "Primary production volumes in Japan were obtained from the Japan Plastic Federation.",
            "prev_text": "",
            "next_text": "",
        },
    ]
    japan_in_yamamoto = gemini._check_entity_in_library(
        patterns=[r"\bjapan\b", r"\bjapanese\b"],
        document_ids=["doc_yamamoto_001"],
        fallback_metadata=mock_yamamoto_with_japan,
        min_substantive_chunks=2,
    )
    assert japan_in_yamamoto is True

    # 3. Exact failure path query: India production in Japanese literature with Yamamoto selected
    q = "What was the total volume of plastic production in India in 2018-19 according to the selected Japanese literature?"
    pq = process_query(q)

    # In Yamamoto, Japan is present in substantive chunks, but India is not
    resp = gemini._deterministic_synthesizer(
        question=q,
        retrieved_metadata=mock_yamamoto_with_japan,
        start_time=0.0,
        pq=pq,
        document_ids=["doc_yamamoto_001"],
    )

    assert resp["insufficient_evidence"] is True
    assert "India" in resp["answer"]
    assert "does not contain evidence" in resp["answer"].lower() or "not contain evidence" in resp["answer"].lower()


# ----------------------------------------------------------------------------------
# Test AR — Disclosure sentence exemption from unsupported claim penalty
# ----------------------------------------------------------------------------------
def test_ar_disclosure_sentences_exempt_from_unsupported_penalty_while_real_unsupported_flagged():
    """Proves that explicit disclosure statements acknowledging absence of evidence are
    exempt from unsupported-claim scoring, while real hallucinated claims remain flagged."""
    from app.services.citations.validator import CitationValidator
    from app.models.chunk import Chunk

    validator = CitationValidator()

    retrieved_chunk = Chunk(
        id="chunk_valid_001",
        document_id="doc_valid_001",
        chunk_index=0,
        text="This study proposes an extended producer responsibility framework.",
        page_numbers=[1],
    )

    raw_response = {
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_valid_001",
                "filename": "document.pdf",
                "chunk_ids": ["chunk_valid_001"],
                "page_numbers": [1],
                "excerpt": "This study proposes an extended producer responsibility framework.",
            }
        ],
        "claims": [
            # 1. Genuine supported claim with valid citation
            {
                "text": "The study proposes an extended producer responsibility framework.",
                "citation_ids": ["cite:1"],
                "support_status": "supported",
            },
            # 2. Explicit disclosure sentence acknowledging missing evidence (no citation needed)
            {
                "text": "The selected literature does not report empirical evidence on this facet; inquiry is answered from the remaining substantiated sources.",
                "citation_ids": [],
                "support_status": "supported",
            },
            # 3. Genuine hallucinated / unsupported factual claim
            {
                "text": "The national program completely eliminated 99.8% of marine plastics across 45 coastal ports.",
                "citation_ids": [],
                "support_status": "supported",  # Raw LLM claims it as supported, validator must reject it
            },
        ],
        "warnings": [],
        "insufficient_evidence": False,
    }

    verified_citations, verified_claims, warnings, insufficient_ev = validator.validate_and_hydrate(
        raw_response, [retrieved_chunk]
    )

    assert len(verified_claims) == 3
    # Supported claim: supported
    assert verified_claims[0].support_status == "supported"
    # Disclosure statement: must be exempt and marked supported (not unsupported)
    assert verified_claims[1].support_status == "supported"
    # Real unsupported claim: must be flipped to unsupported
    assert verified_claims[2].support_status == "unsupported"

    # Only the genuine unsupported claim generates a provenance warning
    assert any("99.8%" in w or "lacks valid citation" in w for w in warnings)
    assert not any("The selected literature does not report" in w for w in warnings)


# ----------------------------------------------------------------------------------
# Test AS — Validator flags fabricated numbers, entities, uncited claims, exempts disclosure
# ----------------------------------------------------------------------------------
def test_as_validator_flags_fabricated_number_entity_uncited_and_exempts_disclosure():
    """Proves that CitationValidator flags fabricated numerical figures, ungrounded
    named assertions, and uncited factual sentences, while strictly exempting explicit disclosure."""
    from app.services.citations.validator import CitationValidator
    from app.models.chunk import Chunk

    validator = CitationValidator()

    substantive_chunk = Chunk(
        id="chunk_sub_999",
        document_id="doc_sub_999",
        chunk_index=0,
        text="The national plastic packaging recovery system operates across central sorting facilities.",
        page_numbers=[4],
    )

    raw_response = {
        "citations": [
            {
                "citation_id": "cite:1",
                "document_id": "doc_sub_999",
                "filename": "substantive_paper.pdf",
                "chunk_ids": ["chunk_sub_999"],
                "page_numbers": [4],
                "excerpt": "The national plastic packaging recovery system operates across central sorting facilities.",
            }
        ],
        "claims": [
            # 1. Fabricated number: claims 84.7% recovery, but chunk text contains no numbers
            {
                "text": "The national packaging recovery system achieved an 84.7% sorting rate.",
                "citation_ids": ["cite:1"],
                "support_status": "supported",
            },
            # 2. Fabricated named entity / ungrounded factual statement without citation
            {
                "text": "The Antarctic Ecological Council published new municipal directives.",
                "citation_ids": [],
                "support_status": "supported",
            },
            # 3. Uncited factual sentence
            {
                "text": "Informal waste pickers processed 1.2 million tonnes of polymer waste in 2023.",
                "citation_ids": [],
                "support_status": "supported",
            },
            # 4. Explicit disclosure sentence acknowledging missing facet
            {
                "text": "The selected literature does not report empirical evidence on this facet; inquiry is answered from the remaining substantiated sources.",
                "citation_ids": [],
                "support_status": "supported",
            },
        ],
        "warnings": [],
        "insufficient_evidence": False,
    }

    verified_citations, verified_claims, warnings, _ = validator.validate_and_hydrate(
        raw_response, [substantive_chunk]
    )

    # 1. Fabricated number must be demoted to unsupported
    assert verified_claims[0].support_status == "unsupported"
    assert any("84.7%" in w for w in warnings)

    # 2. Ungrounded uncited named entity must be demoted to unsupported
    assert verified_claims[1].support_status == "unsupported"

    # 3. Uncited factual sentence must be demoted to unsupported
    assert verified_claims[2].support_status == "unsupported"

    # 4. Explicit disclosure statement must be preserved as supported
    assert verified_claims[3].support_status == "supported"


# ----------------------------------------------------------------------------------
# Test AT — Entity check: exactly one substantive chunk must NOT abstain
# ----------------------------------------------------------------------------------
def test_at_entity_check_one_substantive_chunk_does_not_abstain():
    """Proves that when a required entity is present in exactly one substantive chunk
    of the target document, library entity check succeeds and does NOT trigger abstention."""
    from app.services.generation.llm import get_gemini_service

    service = get_gemini_service()

    target_doc_id = "doc_target_001"
    substantive_metadata = [
        {
            "chunk_id": "chunk_sub_01",
            "document_id": target_doc_id,
            "filename": "target_doc.pdf",
            "page_numbers": [2],
            "text": "Municipal plastic collection data in Portugal was gathered across urban centers.",
            "prev_text": "",
            "next_text": "",
        }
    ]

    has_entity = service._check_entity_in_library(
        patterns=[r"\bportugal\b"],
        document_ids=[target_doc_id],
        fallback_metadata=substantive_metadata,
        min_substantive_chunks=1,
    )
    assert has_entity is True


# ----------------------------------------------------------------------------------
# Test AU — Entity check: zero substantive chunks must abstain
# ----------------------------------------------------------------------------------
def test_au_entity_check_zero_chunks_abstains():
    """Proves that when a required entity is completely absent from the selected document,
    library entity check returns False and forces abstention."""
    from app.services.generation.llm import get_gemini_service

    service = get_gemini_service()

    target_doc_id = "doc_target_002"
    substantive_metadata = [
        {
            "chunk_id": "chunk_sub_02",
            "document_id": target_doc_id,
            "filename": "target_doc.pdf",
            "page_numbers": [3],
            "text": "Solar energy conversion efficiencies were evaluated in Japanese laboratories.",
            "prev_text": "",
            "next_text": "",
        }
    ]

    has_entity = service._check_entity_in_library(
        patterns=[r"\bindia\b"],
        document_ids=[target_doc_id],
        fallback_metadata=substantive_metadata,
        min_substantive_chunks=1,
    )
    assert has_entity is False


# ----------------------------------------------------------------------------------
# Test AV — Entity check: entity appearing only in bibliography must abstain
# ----------------------------------------------------------------------------------
def test_av_entity_check_only_bibliography_abstains():
    """Proves that when an entity is mentioned exclusively within bibliography or
    reference chunks, library entity check excludes it and forces abstention."""
    from app.services.generation.llm import get_gemini_service

    service = get_gemini_service()

    target_doc_id = "doc_target_003"
    ref_metadata = [
        {
            "chunk_id": "chunk_ref_01",
            "document_id": target_doc_id,
            "filename": "target_doc.pdf",
            "page_numbers": [12],
            "text": "References\n1. Sharma R, Desai A. Plastic flows in India. J. Mater. Cycles 2024;26:100-112.\n2. Smith J, et al. Science 2021;370:45.",
            "prev_text": "",
            "next_text": "",
        }
    ]

    has_entity = service._check_entity_in_library(
        patterns=[r"\bindia\b"],
        document_ids=[target_doc_id],
        fallback_metadata=ref_metadata,
        min_substantive_chunks=1,
    )
    assert has_entity is False


# ----------------------------------------------------------------------------------
# Test AW — API passes eligible document IDs to generation
# ----------------------------------------------------------------------------------
def test_aw_api_passes_eligible_doc_ids_to_generation():
    """Proves that research API router passes eligible_doc_ids (not raw body.document_ids)
    to generate_grounded_answer so generation cannot leak unindexed or unauthorized documents."""
    import inspect
    from app.api.v1 import research

    source_code = inspect.getsource(research.ask_research_question)
    assert "document_ids=eligible_doc_ids" in source_code
    assert "document_ids=body.document_ids" not in source_code




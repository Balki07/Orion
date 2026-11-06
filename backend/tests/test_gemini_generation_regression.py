"""Regression tests for Gemini response parsing, error categorization, and generation pipeline."""

import json
import pytest
from unittest.mock import MagicMock, patch

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.citations.validator import CitationValidator
from app.services.generation.llm import (
    GeminiService,
    extract_json_payload,
    _attempt_json_recovery,
)


def test_extract_json_payload_direct_clean():
    payload = '{"answer": "EPR holds producers accountable.", "insufficient_evidence": false, "claims": [], "citations": []}'
    parsed = extract_json_payload(payload)
    assert parsed["answer"] == "EPR holds producers accountable."
    assert parsed["insufficient_evidence"] is False


def test_extract_json_payload_markdown_code_fences():
    # Markdown json fence
    payload_fence = '```json\n{"answer": "Grounded answer with citations [cite:1].", "insufficient_evidence": false}\n```'
    parsed = extract_json_payload(payload_fence)
    assert parsed["answer"] == "Grounded answer with citations [cite:1]."

    # Plain fence without 'json' tag
    payload_plain_fence = '```\n{"answer": "Plain fence answer.", "insufficient_evidence": false}\n```'
    parsed = extract_json_payload(payload_plain_fence)
    assert parsed["answer"] == "Plain fence answer."


def test_extract_json_payload_preamble_and_postamble():
    payload = (
        "Here is the evidence-grounded synthesis matching your schema:\n\n"
        '{"answer": "Synthesis with surrounding prose.", "insufficient_evidence": false, "claims": []}\n\n'
        "I hope this thoroughly addresses your research inquiry."
    )
    parsed = extract_json_payload(payload)
    assert parsed["answer"] == "Synthesis with surrounding prose."


def test_extract_json_payload_unescaped_control_characters():
    # In strict=True, unescaped raw newlines in string crash json.loads
    payload = '{"answer": "First line of answer.\nSecond line of answer.", "insufficient_evidence": false}'
    parsed = extract_json_payload(payload)
    assert "First line" in parsed["answer"]
    assert "Second line" in parsed["answer"]


def test_extract_json_payload_empty_and_none():
    with pytest.raises(ValueError, match="empty text response"):
        extract_json_payload("")

    with pytest.raises(ValueError, match="empty text response"):
        extract_json_payload("   \n\t  ")

    with pytest.raises(ValueError, match="Model returned None"):
        extract_json_payload(None)


def test_extract_json_payload_truncated_recovery():
    # Simulated truncated output where closing braces are missing
    truncated = '{"answer": "Plastic production reached 15.6MT [cite:1]", "insufficient_evidence": false, "claims": [{"text": "Production reached 15.6MT", "citation_ids": ["cite:1"]'
    parsed = extract_json_payload(truncated)
    assert "15.6MT" in parsed["answer"]
    assert any("recovered" in w.lower() or "reconstructed" in w.lower() for w in parsed.get("warnings", []))


def test_error_categorization_distinguishes_quota_vs_json_decode():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    # 1. Test HTTP 429 Quota Exceeded error
    mock_429 = Exception("429 RESOURCE_EXHAUSTED: Generate content requests per day limit exceeded on Free Tier.")
    service._client.models.generate_content.side_effect = mock_429

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India.",
        "chunk_index": 0,
    }]

    import asyncio
    resp_quota = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India.",
            retrieved_metadata=metadata,
        )
    )

    # Must explicitly state 429 quota exhaustion, NOT JSONDecodeError
    warnings = resp_quota.get("warnings", [])
    assert any("quota" in w.lower() or "limit" in w.lower() for w in warnings), f"Expected quota warning, got: {warnings}"
    assert not any("JSONDecodeError" in w for w in warnings), f"Should not claim JSONDecodeError on 429: {warnings}"
    assert resp_quota["model"] is None
    assert resp_quota["answer_path"] == "deterministic_fallback"
    assert resp_quota["fallback_reason"] == "QUOTA"


def test_error_categorization_on_malformed_unrecoverable_json():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    # Simulate successful API response returning totally unparseable garbage
    mock_resp = MagicMock()
    mock_resp.text = "NOT JSON AT ALL AND NO BRACES"
    mock_resp.candidates = [MagicMock(finish_reason="STOP")]
    service._client.models.generate_content.return_value = mock_resp
    service._client.models.generate_content.side_effect = None

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp_malformed = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production in India?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    warnings = resp_malformed.get("warnings", [])
    assert any("response parsing failed" in w.lower() for w in warnings), f"Expected response parsing failure, got: {warnings}"
    assert resp_malformed["model"] is None
    assert resp_malformed["answer_path"] == "deterministic_fallback"
    assert resp_malformed["fallback_reason"] == "OTHER"


def test_successful_gemini_generation_attribution():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "answer": "According to the study, plastic production reached 15.6 million tonnes [cite:1].",
        "insufficient_evidence": False,
        "claims": [{
            "text": "Plastic production reached 15.6 million tonnes.",
            "citation_ids": ["cite:1"],
            "support_status": "supported",
        }],
        "citations": [{
            "citation_id": "cite:1",
            "chunk_ids": ["c1"],
            "document_id": "d1",
            "filename": "test.pdf",
            "page_numbers": [1],
            "excerpt": "Plastic production in India was 15.6 million tonnes.",
        }],
        "warnings": [],
    })
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50, total_token_count=150)
    service._client.models.generate_content.return_value = mock_resp
    service._client.models.generate_content.side_effect = None

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp_success = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production in India?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp_success["answer_path"] == "gemini"
    assert resp_success["model"] == service.model_name
    assert resp_success["fallback_reason"] is None
    assert "15.6 million tonnes" in resp_success["answer"]
    assert len(resp_success["citations"]) == 1
    assert resp_success["insufficient_evidence"] is False
    assert resp_success["usage_metadata"]["total_token_count"] == 150


def test_gemini_429_retry_then_success():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    class MockRetryable429(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        response_json = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "0.1s"}]}}

    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "answer": "Answer after retry [cite:1].",
        "insufficient_evidence": False,
        "claims": [],
        "citations": [{
            "citation_id": "cite:1",
            "chunk_ids": ["c1"],
            "document_id": "d1",
            "filename": "test.pdf",
            "page_numbers": [1],
            "excerpt": "Plastic production in India was 15.6 million tonnes.",
        }],
    })
    mock_resp.usage_metadata = MagicMock(prompt_token_count=50, candidates_token_count=20, total_token_count=70)

    # First call raises retryable 429, second call succeeds
    service._client.models.generate_content.side_effect = [MockRetryable429("Rate limit"), mock_resp]

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp["answer_path"] == "gemini"
    assert resp["model"] == service.model_name
    assert resp["fallback_reason"] is None
    assert "Answer after retry" in resp["answer"]
    assert service._client.models.generate_content.call_count == 2


def test_gemini_persistent_429_falls_back_quota():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    class MockDaily429(Exception):
        code = 429
        status = "RESOURCE_EXHAUSTED"
        response_json = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [{"retryDelay": "15000s"}]}}

    service._client.models.generate_content.side_effect = MockDaily429("Daily quota exhausted")

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp["answer_path"] == "deterministic_fallback"
    assert resp["model"] is None
    assert resp["fallback_reason"] == "QUOTA"
    assert any("daily limit" in w.lower() for w in resp.get("warnings", []))


def test_gemini_404_model_not_found():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    class Mock404(Exception):
        code = 404
        status = "NOT_FOUND"

    service._client.models.generate_content.side_effect = Mock404("Model models/gemini-not-found is not found")

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp["answer_path"] == "deterministic_fallback"
    assert resp["model"] is None
    assert resp["fallback_reason"] == "MODEL_NOT_FOUND"
    assert any("model not found" in w.lower() for w in resp.get("warnings", []))


def test_gemini_403_bad_key():
    service = GeminiService()
    service._client = MagicMock()
    GeminiService._quota_exhausted_until = 0.0

    class Mock403(Exception):
        code = 403
        status = "PERMISSION_DENIED"

    service._client.models.generate_content.side_effect = Mock403("API key not valid. Please pass a valid API key.")

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp["answer_path"] == "deterministic_fallback"
    assert resp["model"] is None
    assert resp["fallback_reason"] == "BAD_KEY"
    assert any("key problem" in w.lower() for w in resp.get("warnings", []))


def test_gemini_missing_key():
    service = GeminiService()
    service.api_key = ""
    service._client = None
    GeminiService._quota_exhausted_until = 0.0

    metadata = [{
        "chunk_id": "c1",
        "document_id": "d1",
        "filename": "test.pdf",
        "page_numbers": [1],
        "text": "Plastic production in India was 15.6 million tonnes.",
        "chunk_index": 0,
    }]

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What was plastic production?",
            formatted_context="Plastic production in India was 15.6 million tonnes.",
            retrieved_metadata=metadata,
        )
    )

    assert resp["answer_path"] == "deterministic_fallback"
    assert resp["model"] is None
    assert resp["fallback_reason"] == "KEY_NOT_LOADED"
    assert any("key not configured" in w.lower() for w in resp.get("warnings", []))


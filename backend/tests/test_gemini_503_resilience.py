"""Comprehensive verification tests for Gemini 503 resilience, latency reduction,
non-retryable error fail-fast, fallback model support, citation validation, and auth behavior.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User, UserSession
from app.schemas.research import AskResponse
from app.security.service import create_session_jwt, hash_password, hash_token
from app.services.citations.validator import CitationValidator
from app.services.generation.llm import (
    FALLBACK_REASON_BAD_KEY,
    FALLBACK_REASON_MODEL_NOT_FOUND,
    FALLBACK_REASON_NETWORK,
    FALLBACK_REASON_QUOTA,
    FALLBACK_REASON_UNAVAILABLE,
    PLAIN_FALLBACK_MESSAGES,
    GeminiService,
    classify_gemini_error,
    is_retryable_gemini_error,
)


@pytest.fixture
def mock_retrieved_metadata():
    return [
        {
            "chunk_id": "chk_epr_01",
            "document_id": "doc_pilot_01",
            "filename": "epr_policy_framework.pdf",
            "page_numbers": [3],
            "text": "Extended Producer Responsibility requires brand owners to achieve 70% post-consumer collection targets.",
            "chunk_index": 0,
            "prev_text": "",
            "next_text": "",
        },
        {
            "chunk_id": "chk_epr_02",
            "document_id": "doc_pilot_01",
            "filename": "epr_policy_framework.pdf",
            "page_numbers": [4],
            "text": "Under the 2026 guidelines, recycling targets for rigid plastics increase to 60%.",
            "chunk_index": 1,
            "prev_text": "",
            "next_text": "",
        },
    ]


@pytest.fixture
def mock_chunks():
    d = Document(id="doc_pilot_01", filename="epr_policy_framework.pdf", owner_id="usr_test")
    c1 = Chunk(
        id="chk_epr_01",
        document_id="doc_pilot_01",
        chunk_index=0,
        page_numbers=[3],
        text="Extended Producer Responsibility requires brand owners to achieve 70% post-consumer collection targets.",
    )
    c1.document = d
    c2 = Chunk(
        id="chk_epr_02",
        document_id="doc_pilot_01",
        chunk_index=1,
        page_numbers=[4],
        text="Under the 2026 guidelines, recycling targets for rigid plastics increase to 60%.",
    )
    c2.document = d
    return [c1, c2]


# --- 1. Gemini 503 Response & Classification Tests ---

def test_classify_gemini_503_unavailable():
    """Verify that HTTP 503 and high-demand errors classify as FALLBACK_REASON_UNAVAILABLE."""
    # Simulation 1: Exception with status code 503
    exc_503 = Exception("503 UNAVAILABLE: The model is overloaded. Please try again later.")
    reason, code, status_str, safe_msg = classify_gemini_error(exc_503)
    assert reason == FALLBACK_REASON_UNAVAILABLE
    assert code == 503
    assert "overloaded" in safe_msg.lower()

    # Simulation 2: Object with code attribute
    mock_exc = MagicMock(spec=Exception)
    mock_exc.code = 503
    mock_exc.status = "UNAVAILABLE"
    mock_exc.__str__ = lambda self: "The model gemini-3.5-flash-lite is experiencing high demand."
    reason2, code2, status_str2, safe_msg2 = classify_gemini_error(mock_exc)
    assert reason2 == FALLBACK_REASON_UNAVAILABLE
    assert code2 == 503
    assert status_str2 == "UNAVAILABLE"

    # Simulation 3: Plain text matching high demand
    exc_demand = Exception("model experiencing high demand, please retry later")
    reason3, _, _, _ = classify_gemini_error(exc_demand)
    assert reason3 == FALLBACK_REASON_UNAVAILABLE

    # Message check: user-friendly message
    assert "503" in PLAIN_FALLBACK_MESSAGES[FALLBACK_REASON_UNAVAILABLE]
    assert "research literature" in PLAIN_FALLBACK_MESSAGES[FALLBACK_REASON_UNAVAILABLE]


# --- 2. Bounded Retry & Prompt Fallback Activation Tests ---

@pytest.mark.asyncio
async def test_gemini_503_bounded_retry_and_prompt_fallback(mock_retrieved_metadata):
    """Verify that 503 overload retries at most once and promptly activates deterministic fallback."""
    service = GeminiService()
    service._client = MagicMock()
    service.api_key = "test_key_dummy"

    # Always return 503
    err_503 = Exception("503 The model is overloaded. Please try again later.")
    service._client.models.generate_content.side_effect = err_503

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("app.services.generation.llm.record_llm_usage", new_callable=AsyncMock):
        
        resp = await service.generate_grounded_answer(
            question="What are the collection targets under EPR?",
            formatted_context="Sample context",
            retrieved_metadata=mock_retrieved_metadata,
        )

        # Max attempts for 503 is bounded to 2 (1 initial + 1 retry)
        assert service._client.models.generate_content.call_count == 2
        # Exactly one sleep was called (for the single retry)
        assert mock_sleep.call_count == 1

        # Check response metadata
        assert resp["answer_path"] == "deterministic_fallback"
        assert resp["model"] is None
        assert resp["fallback_reason"] == FALLBACK_REASON_UNAVAILABLE
        assert any("503" in w for w in resp.get("warnings", []))

        # Check generation diagnostics
        diag = resp.get("generation_diagnostics", {})
        assert diag["provider"] == "gemini"
        assert diag["attempts"] == 2
        assert diag["fallback_activated"] is True
        assert diag["fallback_reason"] == FALLBACK_REASON_UNAVAILABLE


# --- 3. Non-Retryable Error Fail-Fast Tests ---

@pytest.mark.parametrize(
    "error_text,expected_reason,expected_code",
    [
        ("400 INVALID_ARGUMENT: Invalid JSON schema format", "OTHER", 400),
        ("401 UNAUTHENTICATED: API_KEY_INVALID", FALLBACK_REASON_BAD_KEY, 401),
        ("403 PERMISSION_DENIED: Method not allowed for this key", FALLBACK_REASON_BAD_KEY, 403),
        ("404 NOT_FOUND: models/unknown-gemini-model is not found", FALLBACK_REASON_MODEL_NOT_FOUND, 404),
    ],
)
@pytest.mark.asyncio
async def test_non_retryable_errors_fail_fast(mock_retrieved_metadata, error_text, expected_reason, expected_code):
    """Verify that non-retryable errors fail immediately without wasting time on retries."""
    service = GeminiService()
    service._client = MagicMock()
    service.api_key = "test_key_dummy"

    err = Exception(error_text)
    service._client.models.generate_content.side_effect = err

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("app.services.generation.llm.record_llm_usage", new_callable=AsyncMock):
        
        resp = await service.generate_grounded_answer(
            question="What are the collection targets?",
            formatted_context="Sample context",
            retrieved_metadata=mock_retrieved_metadata,
        )

        # Call count must be EXACTLY 1 (ZERO retries)
        assert service._client.models.generate_content.call_count == 1
        assert mock_sleep.call_count == 0

        assert resp["answer_path"] == "deterministic_fallback"
        assert resp["model"] is None
        diag = resp.get("generation_diagnostics", {})
        assert diag["attempts"] == 1
        assert diag["fallback_activated"] is True


def test_is_retryable_helper():
    """Unit test for is_retryable_gemini_error matrix."""
    assert is_retryable_gemini_error(503, "UNAVAILABLE", FALLBACK_REASON_UNAVAILABLE, None) is True
    assert is_retryable_gemini_error(429, "RESOURCE_EXHAUSTED", FALLBACK_REASON_QUOTA, 2.0) is True
    assert is_retryable_gemini_error(None, None, FALLBACK_REASON_NETWORK, None) is True

    # Non-retryable
    assert is_retryable_gemini_error(400, "INVALID_ARGUMENT", "OTHER", None) is False
    assert is_retryable_gemini_error(401, "UNAUTHENTICATED", FALLBACK_REASON_BAD_KEY, None) is False
    assert is_retryable_gemini_error(403, "PERMISSION_DENIED", FALLBACK_REASON_BAD_KEY, None) is False
    assert is_retryable_gemini_error(404, "NOT_FOUND", FALLBACK_REASON_MODEL_NOT_FOUND, None) is False
    assert is_retryable_gemini_error(429, "RESOURCE_EXHAUSTED", FALLBACK_REASON_QUOTA, 120.0) is False


# --- 4. Optional Alternative Fallback Model Support ---

@pytest.mark.asyncio
async def test_optional_fallback_model_success(mock_retrieved_metadata):
    """Verify that if GEMINI_FALLBACK_MODEL is configured, failure of primary model triggers fallback model."""
    service = GeminiService()
    service._client = MagicMock()
    service.api_key = "test_key_dummy"

    # Primary model fails with 503; Fallback model succeeds
    mock_success_response = MagicMock()
    mock_success_response.text = json.dumps({
        "answer": "Under EPR guidelines, collection targets require 70% [cite:1].",
        "insufficient_evidence": False,
        "claims": [{
            "text": "Collection targets require 70%",
            "citation_ids": ["cite:1"],
            "support_status": "supported",
        }],
        "citations": [{
            "citation_id": "cite:1",
            "chunk_ids": ["chk_epr_01"],
            "document_id": "doc_pilot_01",
            "filename": "epr_policy_framework.pdf",
            "page_numbers": [3],
            "excerpt": "Extended Producer Responsibility requires brand owners to achieve 70% post-consumer collection targets.",
        }],
        "warnings": [],
    })
    mock_success_response.usage_metadata = MagicMock(prompt_token_count=80, candidates_token_count=40, total_token_count=120)

    def side_effect_fn(*args, **kwargs):
        model = kwargs.get("model", "")
        if "fallback" in model or model == "gemini-2.5-flash-lite":
            return mock_success_response
        raise Exception("503 UNAVAILABLE: Model is overloaded.")

    service._client.models.generate_content.side_effect = side_effect_fn

    with patch.object(settings, "GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite"), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("app.services.generation.llm.record_llm_usage", new_callable=AsyncMock):
        
        resp = await service.generate_grounded_answer(
            question="What are the collection targets?",
            formatted_context="Sample context",
            retrieved_metadata=mock_retrieved_metadata,
        )

        assert resp["answer_path"] == "gemini"
        assert resp["model"] == "gemini-2.5-flash-lite"
        assert "70%" in resp["answer"]
        assert any("fallback model 'gemini-2.5-flash-lite'" in w for w in resp.get("warnings", []))
        diag = resp.get("generation_diagnostics", {})
        assert diag["actual_model"] == "gemini-2.5-flash-lite"
        assert diag["fallback_model_attempted"] is True
        assert diag["fallback_activated"] is False


# --- 5. Citation Validation After Fallback ---

def test_citation_validation_after_fallback(mock_chunks, mock_retrieved_metadata):
    """Verify that citation validation functions rigorously on deterministic fallback answers."""
    service = GeminiService()
    service._client = None  # Force immediate deterministic fallback

    import asyncio
    resp = asyncio.run(
        service.generate_grounded_answer(
            question="What are the collection targets under EPR?",
            formatted_context="Context",
            retrieved_metadata=mock_retrieved_metadata,
        )
    )

    validator = CitationValidator()
    verified_citations, verified_claims, warnings, insufficient_evidence = (
        validator.validate_and_hydrate(resp, mock_chunks)
    )

    assert not insufficient_evidence
    assert len(verified_citations) >= 1
    # Check that hydrated citation points to correct page and file
    first_cite = verified_citations[0]
    assert first_cite.document_id == "doc_pilot_01"
    assert first_cite.filename == "epr_policy_framework.pdf"
    assert first_cite.page_numbers in ([3], [4], [3, 4])
    assert len(first_cite.excerpt) > 10


# --- 6. Authentication Behavior & 401 Investigation ---

@pytest.mark.asyncio
async def test_auth_me_unauthenticated_probe():
    """Verify that an initial unauthenticated GET /api/v1/auth/me returns 401 as expected."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/api/v1/auth/me")
            assert res.status_code == 401
            data = res.json()
            assert "Authentication credentials were not provided or are invalid" in data.get("detail", "")
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_auth_me_expired_session():
    """Verify that an expired JWT token returns HTTP 401 with explicit expired detail."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        expired_token = create_session_jwt(
            user_id="usr_test_expired",
            email="expired@orion.ai",
            session_id="sess_expired",
            expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        )
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401
        data = res.json()
        assert "expired" in data.get("detail", "").lower()

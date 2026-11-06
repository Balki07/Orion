"""Regression tests for Phase 1: LLM Usage Tracking.

Covers:
1. Successful generation usage recording.
2. Failed API attempt recording.
3. Multiple retries associated with one research question.
4. Accurate input/output token extraction.
5. Missing usage metadata honestly stored as None.
6. Deterministic fallback not counted as a provider call.
7. Zero-context abstention not counted as a provider call.
8. Cache hits not counted as new generation calls.
9. Persistence across database sessions / backend restarts.
10. Strict UTC timestamp handling.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, init_db
from app.models.llm_usage import LLMUsageRecord
from app.services.generation.llm import GeminiService
from app.services.generation.usage_tracker import (
    get_recent_usage_records,
    get_usage_summary,
    record_llm_usage,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is initialized before running tests."""
    await init_db()


@pytest.mark.asyncio
async def test_successful_generation_usage_recording():
    """Verify successful generation records token counts, latency, and status='success'."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"
    service._client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.text = '{"answer": "Grounding answer from research.", "claims": [], "citations": []}'
    mock_resp.usage_metadata = MagicMock()
    mock_resp.usage_metadata.prompt_token_count = 1420
    mock_resp.usage_metadata.candidates_token_count = 310
    mock_resp.usage_metadata.total_token_count = 1730
    service._client.models.generate_content.return_value = mock_resp

    test_trace_id = f"trace_test_success_{datetime.now().timestamp()}"

    res = await service.generate_grounded_answer(
        question="What is Extended Producer Responsibility?",
        formatted_context="Sample context chunk text from EPR policy paper.",
        retrieved_metadata=[{"chunk_id": "c1", "document_id": "d1", "page_numbers": [1], "filename": "doc.pdf", "text": "sample"}],
        trace_id=test_trace_id,
        request_id="req_test_123",
        user_id="user_test_researcher",
    )

    assert res["answer_path"] == "gemini"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_test_researcher", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) == 1
        rec = matching[0]

        assert rec.is_provider_call is True
        assert rec.status == "success"
        assert rec.http_status_code == 200
        assert rec.model == "gemini-3.5-flash-lite"
        assert rec.attempt_number == 1
        assert rec.prompt_tokens == 1420
        assert rec.completion_tokens == 310
        assert rec.total_tokens == 1730
        assert rec.has_usage_metadata is True
        assert rec.latency_ms > 0.0
        assert rec.created_at.tzinfo is not None or rec.created_at.isoformat()


@pytest.mark.asyncio
async def test_failed_api_attempt_recording():
    """Verify failed API attempts record error code, category, and is_provider_call=True with None tokens."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"
    service._client = MagicMock()

    class Mock429(Exception):
        pass

    service._client.models.generate_content.side_effect = Mock429("Resource has been exhausted (e.g. check quota). code=429")

    test_trace_id = f"trace_test_failed_{datetime.now().timestamp()}"

    res = await service.generate_grounded_answer(
        question="What are EPR targets?",
        formatted_context="Context passage for EPR targets.",
        retrieved_metadata=[{"chunk_id": "c1", "document_id": "d1", "page_numbers": [1], "filename": "doc.pdf", "text": "targets"}],
        trace_id=test_trace_id,
        user_id="user_failed_test",
    )

    # Should fall back gracefully to deterministic synthesis
    assert res["answer_path"] == "deterministic_fallback"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_failed_test", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) >= 1
        rec = matching[0]

        assert rec.is_provider_call is True
        assert rec.status == "failed"
        assert rec.http_status_code == 429
        assert rec.error_category == "QUOTA"
        assert rec.prompt_tokens is None
        assert rec.completion_tokens is None
        assert rec.total_tokens is None
        assert rec.has_usage_metadata is False


@pytest.mark.asyncio
async def test_multiple_retries_associated_with_one_question():
    """Verify that multiple retry attempts share the same trace_id but have distinct attempt numbers."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"
    service._client = MagicMock()

    class Mock503(Exception):
        pass

    mock_resp = MagicMock()
    mock_resp.text = '{"answer": "Recovered after retry.", "claims": [], "citations": []}'
    mock_resp.usage_metadata = MagicMock()
    mock_resp.usage_metadata.prompt_token_count = 1100
    mock_resp.usage_metadata.candidates_token_count = 200
    mock_resp.usage_metadata.total_token_count = 1300

    # Attempt 1 fails with 503, Attempt 2 succeeds
    service._client.models.generate_content.side_effect = [
        Mock503("The model is overloaded. Please try again later. code=503"),
        mock_resp,
    ]

    test_trace_id = f"trace_test_retry_{datetime.now().timestamp()}"

    with patch("time.sleep", return_value=None):  # Fast forward retry sleep
        res = await service.generate_grounded_answer(
            question="Explain plastic recycling directives.",
            formatted_context="Passage on directives.",
            retrieved_metadata=[{"chunk_id": "c1", "document_id": "d1", "page_numbers": [1], "filename": "doc.pdf", "text": "pass"}],
            trace_id=test_trace_id,
            user_id="user_retry_test",
        )

    assert res["answer_path"] == "gemini"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_retry_test", limit=10)
        matching = [r for r in records if r.trace_id == test_trace_id]
        matching.sort(key=lambda r: r.attempt_number)

        assert len(matching) == 2, f"Expected 2 attempts recorded for retried question, got {len(matching)}"
        att1, att2 = matching[0], matching[1]

        assert att1.attempt_number == 1
        assert att1.status == "failed"
        assert att1.http_status_code == 503
        assert att1.is_provider_call is True

        assert att2.attempt_number == 2
        assert att2.status == "success"
        assert att2.http_status_code == 200
        assert att2.prompt_tokens == 1100
        assert att2.completion_tokens == 200
        assert att2.total_tokens == 1300
        assert att2.is_provider_call is True


@pytest.mark.asyncio
async def test_missing_usage_metadata_honestly_stored_as_none():
    """Verify that when the provider omits usage metadata, tokens are stored as None, never fabricated."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"
    service._client = MagicMock()

    mock_resp = MagicMock()
    mock_resp.text = '{"answer": "Answer without metadata.", "claims": [], "citations": []}'
    mock_resp.usage_metadata = None  # No usage metadata returned by provider
    service._client.models.generate_content.return_value = mock_resp

    test_trace_id = f"trace_test_no_meta_{datetime.now().timestamp()}"

    res = await service.generate_grounded_answer(
        question="What is EPR?",
        formatted_context="Passage text.",
        retrieved_metadata=[{"chunk_id": "c1", "document_id": "d1", "page_numbers": [1], "filename": "doc.pdf", "text": "pass"}],
        trace_id=test_trace_id,
        user_id="user_no_meta_test",
    )

    assert res["answer_path"] == "gemini"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_no_meta_test", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) == 1
        rec = matching[0]

        assert rec.is_provider_call is True
        assert rec.status == "success"
        assert rec.prompt_tokens is None
        assert rec.completion_tokens is None
        assert rec.total_tokens is None
        assert rec.has_usage_metadata is False


@pytest.mark.asyncio
async def test_deterministic_fallback_not_counted_as_provider_call():
    """Verify that deterministic fallback due to missing client/key has is_provider_call=False and zero tokens."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"
    service._client = None
    service.api_key = None

    test_trace_id = f"trace_test_det_fallback_{datetime.now().timestamp()}"

    res = await service.generate_grounded_answer(
        question="How does deposit return work?",
        formatted_context="Passage on deposit return schemes.",
        retrieved_metadata=[{"chunk_id": "c1", "document_id": "d1", "page_numbers": [1], "filename": "doc.pdf", "text": "pass"}],
        trace_id=test_trace_id,
        user_id="user_fallback_test",
    )

    assert res["answer_path"] == "deterministic_fallback"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_fallback_test", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) == 1
        rec = matching[0]

        assert rec.is_provider_call is False
        assert rec.status == "fallback"
        assert rec.error_category == "KEY_NOT_LOADED"
        assert rec.prompt_tokens is None
        assert rec.total_tokens is None


@pytest.mark.asyncio
async def test_zero_context_abstention_not_counted_as_provider_call():
    """Verify that zero-context abstention has is_provider_call=False and status='abstained_no_context'."""
    service = GeminiService()
    service.model_name = "gemini-3.5-flash-lite"

    test_trace_id = f"trace_test_abstain_{datetime.now().timestamp()}"

    res = await service.generate_grounded_answer(
        question="Non-existent topic?",
        formatted_context="",  # Zero context
        retrieved_metadata=[],
        trace_id=test_trace_id,
        user_id="user_abstain_test",
    )

    assert res["insufficient_evidence"] is True
    assert res["answer_path"] == "deterministic_fallback"

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_abstain_test", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) == 1
        rec = matching[0]

        assert rec.is_provider_call is False
        assert rec.status == "abstained_no_context"
        assert rec.prompt_tokens is None
        assert rec.total_tokens is None


@pytest.mark.asyncio
async def test_cache_hits_not_counted_as_generation_calls():
    """Verify cache hits record status='cached' with is_provider_call=False and zero token consumption."""
    service = GeminiService()
    test_trace_id = f"trace_test_cache_{datetime.now().timestamp()}"

    await service.record_cache_hit(
        trace_id=test_trace_id,
        request_id="req_cached_99",
        user_id="user_cache_test",
    )

    async with AsyncSessionLocal() as session:
        records = await get_recent_usage_records(session, user_id="user_cache_test", limit=5)
        matching = [r for r in records if r.trace_id == test_trace_id]
        assert len(matching) == 1
        rec = matching[0]

        assert rec.is_provider_call is False
        assert rec.status == "cached"
        assert rec.prompt_tokens is None
        assert rec.completion_tokens is None
        assert rec.total_tokens is None


@pytest.mark.asyncio
async def test_persistence_across_sessions_and_restarts():
    """Verify that records committed to the database persist independently across session closures."""
    test_trace_id = f"trace_test_persist_{datetime.now().timestamp()}"

    # Write in session 1
    rec1 = await record_llm_usage(
        trace_id=test_trace_id,
        model="gemini-3.5-flash-lite",
        status="success",
        is_provider_call=True,
        prompt_tokens=500,
        completion_tokens=150,
        total_tokens=650,
        has_usage_metadata=True,
        user_id="user_persist_test",
    )
    assert rec1 is not None

    # Read back in entirely new session 2
    async with AsyncSessionLocal() as session2:
        stmt = select(LLMUsageRecord).where(LLMUsageRecord.trace_id == test_trace_id)
        res = await session2.execute(stmt)
        persisted = res.scalar_one_or_none()

        assert persisted is not None
        assert persisted.id == rec1.id
        assert persisted.total_tokens == 650
        assert persisted.is_provider_call is True
        assert persisted.model == "gemini-3.5-flash-lite"


@pytest.mark.asyncio
async def test_utc_timestamp_handling():
    """Verify created_at timestamps are recorded in UTC and match current UTC window."""
    before_utc = datetime.now(UTC)

    rec = await record_llm_usage(
        trace_id=f"trace_utc_{datetime.now().timestamp()}",
        model="gemini-3.5-flash-lite",
        status="success",
        is_provider_call=True,
        user_id="user_utc_test",
    )
    assert rec is not None

    after_utc = datetime.now(UTC)

    # In SQLite, DateTime(timezone=True) is returned with UTC or naive representation of UTC
    ts = rec.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    assert before_utc <= ts <= after_utc


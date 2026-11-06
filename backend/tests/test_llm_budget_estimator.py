"""
Test suite for Phase 3.1: Question-Budget Estimator Time Horizon Separation.

Validates:
1. Low RPM limit does not reduce daily RPD-based capacity.
2. Low TPM limit does not reduce daily RPD-based capacity.
3. Daily capacity correctly changes when RPD is exhausted.
4. Immediate capacity correctly changes when RPM or TPM is exhausted.
5. Retry factors are applied independently to both estimates.
6. Zero capacity is handled cleanly without negative numbers or exceptions.
7. API response clearly distinguishes daily and immediate estimates.
8. Deterministic fallback, zero-context abstention, and cache-hit exclusion.
9. Missing token metadata handling without NaN or corruption.
10. Insufficient historical samples fallback behavior (low sample size, low confidence).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from conftest import TestSessionLocal

from app.models.llm_quota import LLMQuotaConfig
from app.models.llm_usage import LLMUsageRecord
from app.services.generation.quota_service import (
    get_daily_quota_boundary_utc,
    get_or_create_quota_config,
    get_question_budget_estimate,
)


@pytest.mark.asyncio
async def test_low_rpm_does_not_reduce_daily_rpd_capacity():
    """Verify rolling RPM throughput does NOT depress daily RPD-based question capacity."""
    test_model = f"test-rpm-indep-{uuid4().hex[:6]}"
    async with TestSessionLocal() as session:
        cfg = await get_or_create_quota_config(session, model_id=test_model)
        # 500 RPD with 10% safety margin -> 450 usable requests
        # Conservative attempts = 1.15 -> floor(450 / 1.15) = 391 daily questions
        cfg.rpd_limit = 500
        # Very low RPM: 2 RPM with 10% margin -> 1 usable request -> 0 immediate questions
        cfg.rpm_limit = 2
        cfg.tpm_limit = 250000
        cfg.safety_margin_percent = 0.10
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        # Daily capacity remains high based on RPD, untouched by minute-level RPM
        assert estimate.daily_questions_remaining == 391
        assert estimate.daily_limiting_quota == "RPD"

        # Immediate rolling minute capacity is tightly constrained by RPM
        assert estimate.immediate_questions_conservative <= 1
        assert estimate.immediate_limiting_quota == "RPM"


@pytest.mark.asyncio
async def test_low_tpm_does_not_reduce_daily_rpd_capacity():
    """Verify rolling TPM throughput does NOT depress daily RPD-based question capacity."""
    test_model = f"test-tpm-indep-{uuid4().hex[:6]}"
    async with TestSessionLocal() as session:
        cfg = await get_or_create_quota_config(session, model_id=test_model)
        cfg.rpd_limit = 500
        cfg.rpm_limit = 15
        # Very low TPM: 3000 TPM with 10% margin -> 2700 usable tokens
        # Standard conservative tokens ~ 6625 -> 0 immediate questions
        cfg.tpm_limit = 3000
        cfg.safety_margin_percent = 0.10
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        # Daily capacity must remain 391 based on RPD
        assert estimate.daily_questions_remaining == 391
        assert estimate.daily_limiting_quota == "RPD"

        # Immediate minute capacity is throttled by TPM
        assert estimate.immediate_questions_conservative == 0
        assert estimate.immediate_limiting_quota == "TPM"


@pytest.mark.asyncio
async def test_daily_capacity_exhausted_when_rpd_reaches_zero():
    """Verify daily capacity becomes 0 when RPD is exhausted, regardless of open rolling window."""
    test_model = f"test-rpd-zero-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        cfg = await get_or_create_quota_config(session, model_id=test_model)
        cfg.rpd_limit = 2
        cfg.rpm_limit = 15
        cfg.tpm_limit = 250000
        cfg.safety_margin_percent = 0.0  # Usable RPD = 2
        await session.commit()

        # Add 2 provider requests today (inside today's quota boundary, outside 60s rolling window)
        today_start = get_daily_quota_boundary_utc(cfg.quota_timezone)
        recs = [
            LLMUsageRecord(
                request_id=f"req-{uuid4().hex[:8]}",
                trace_id=f"trc-rpd-{i}",
                model=test_model,
                is_provider_call=True,
                status="success",
                created_at=today_start + timedelta(minutes=1 + i),
            )
            for i in range(2)
        ]
        session.add_all(recs)
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.remaining_requests_today == 0
        assert estimate.daily_questions_remaining == 0
        assert estimate.daily_questions_typical == 0
        assert estimate.daily_questions_optimistic == 0
        assert estimate.daily_limiting_quota == "RPD"

        # Rolling minute window is still open
        assert estimate.rolling_requests_remaining == 15
        assert estimate.immediate_questions_conservative > 0


@pytest.mark.asyncio
async def test_immediate_capacity_exhausted_when_rpm_or_tpm_reaches_zero():
    """Verify immediate capacity reflects rolling window throttling without zeroing daily RPD."""
    test_model = f"test-imm-zero-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        cfg = await get_or_create_quota_config(session, model_id=test_model)
        cfg.rpd_limit = 500
        cfg.rpm_limit = 3
        cfg.tpm_limit = 250000
        cfg.safety_margin_percent = 0.0
        await session.commit()

        # Fill rolling 60s window with 3 provider calls
        recs = [
            LLMUsageRecord(
                request_id=f"req-{uuid4().hex[:8]}",
                trace_id=f"trc-imm-{i}",
                model=test_model,
                is_provider_call=True,
                status="success",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                has_usage_metadata=True,
                created_at=now - timedelta(seconds=10 * (i + 1)),
            )
            for i in range(3)
        ]
        session.add_all(recs)
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        # Immediate window is exhausted
        assert estimate.rolling_requests_remaining == 0
        assert estimate.immediate_questions_conservative == 0
        assert estimate.immediate_limiting_quota == "RPM"

        # Daily capacity remains healthy (497 remaining requests)
        assert estimate.remaining_requests_today == 497
        assert estimate.daily_questions_remaining > 400


@pytest.mark.asyncio
async def test_retry_factors_applied_independently():
    """Verify retry attempt ratios scale both daily and immediate estimates consistently."""
    test_model = f"test-retry-both-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        await get_or_create_quota_config(session, model_id=test_model)

        # Question 1: 1 attempt
        rec1 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_q1",
            model=test_model,
            is_provider_call=True,
            status="success",
            prompt_tokens=2000,
            completion_tokens=500,
            total_tokens=2500,
            has_usage_metadata=True,
            created_at=now - timedelta(minutes=5),
        )
        # Question 2: 2 attempts (retry)
        rec2_f = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_q2",
            model=test_model,
            attempt_number=1,
            is_provider_call=True,
            status="failed",
            error_category="RESOURCE_EXHAUSTED",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            has_usage_metadata=False,
            created_at=now - timedelta(minutes=4),
        )
        rec2_s = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_q2",
            model=test_model,
            attempt_number=2,
            is_provider_call=True,
            status="success",
            prompt_tokens=2100,
            completion_tokens=600,
            total_tokens=2700,
            has_usage_metadata=True,
            created_at=now - timedelta(minutes=3),
        )

        session.add_all([rec1, rec2_f, rec2_s])
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.attempts_per_question == 1.5
        # Conservative attempts = 1.5 * 1.15 = 1.72
        # Daily requests = 450 - 3 = 447 -> floor(447 / 1.72) = 259 questions
        assert estimate.daily_questions_remaining == 259
        # Immediate requests = 13 -> floor(13 / 1.72) = 7 questions
        assert estimate.immediate_questions_conservative == 7


@pytest.mark.asyncio
async def test_cache_hit_and_fallback_exclusion():
    """Verify deterministic fallbacks and cache hits are excluded from provider statistics."""
    test_model = f"test-excl-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        await get_or_create_quota_config(session, model_id=test_model)

        rec_real = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_real",
            model=test_model,
            is_provider_call=True,
            status="success",
            prompt_tokens=1500,
            completion_tokens=500,
            total_tokens=2000,
            has_usage_metadata=True,
            created_at=now - timedelta(minutes=10),
        )
        rec_fallback = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_fallback",
            model=test_model,
            is_provider_call=False,
            status="fallback",
            created_at=now - timedelta(minutes=8),
        )
        rec_cached = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_cached",
            model=test_model,
            is_provider_call=False,
            status="cached",
            created_at=now - timedelta(minutes=6),
        )

        session.add_all([rec_real, rec_fallback, rec_cached])
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.sample_size == 1
        assert estimate.average_total_tokens == 2000
        assert estimate.attempts_per_question == 1.0


@pytest.mark.asyncio
async def test_missing_token_metadata_handling():
    """Verify calls with omitted provider usage metadata do not corrupt averages."""
    test_model = f"test-nometa-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        await get_or_create_quota_config(session, model_id=test_model)

        rec1 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_valid",
            model=test_model,
            is_provider_call=True,
            status="success",
            prompt_tokens=3000,
            completion_tokens=1000,
            total_tokens=4000,
            has_usage_metadata=True,
            created_at=now - timedelta(minutes=5),
        )
        rec2 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id="trc_none",
            model=test_model,
            is_provider_call=True,
            status="success",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            has_usage_metadata=False,
            created_at=now - timedelta(minutes=4),
        )

        session.add_all([rec1, rec2])
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.sample_size == 1
        assert estimate.average_total_tokens == 4000
        assert estimate.average_prompt_tokens == 3000
        assert estimate.average_completion_tokens == 1000


@pytest.mark.asyncio
async def test_insufficient_historical_samples_fallback_behavior():
    """Verify low sample size triggers conservative fallback estimates and low confidence."""
    test_model = f"test-sample-{uuid4().hex[:6]}"
    async with TestSessionLocal() as session:
        await get_or_create_quota_config(session, model_id=test_model)

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.sample_size == 0
        assert estimate.is_fallback_estimate is True
        assert estimate.confidence == "low"
        assert estimate.average_prompt_tokens == 3500
        assert estimate.average_completion_tokens == 1800
        assert estimate.average_total_tokens == 5300
        assert "Preliminary budget projection" in estimate.estimation_disclaimer
        assert estimate.remaining_tokens_today is None


@pytest.mark.asyncio
async def test_safety_margin_application():
    """Verify safety reserve margin is deducted before calculating usable capacity."""
    test_model = f"test-margin-{uuid4().hex[:6]}"
    async with TestSessionLocal() as session:
        cfg = await get_or_create_quota_config(session, model_id=test_model)
        cfg.rpd_limit = 100
        cfg.rpm_limit = 10
        cfg.safety_margin_percent = 0.20
        await session.commit()

        estimate = await get_question_budget_estimate(session, model_id=test_model)

        assert estimate.remaining_requests_today == 80
        assert estimate.rolling_requests_remaining == 8
        assert estimate.safety_margin_percent == 0.20


@pytest.mark.asyncio
async def test_api_get_llm_quota_estimate_endpoint(client):
    """GET /api/v1/settings/llm-quota/estimate clearly distinguishes daily and immediate estimates."""
    resp = await client.get("/api/v1/settings/llm-quota/estimate")
    assert resp.status_code == 200
    data = resp.json()

    # Daily Horizon
    assert "daily_questions_remaining" in data
    assert "daily_questions_typical" in data
    assert "daily_questions_optimistic" in data
    assert data["daily_limiting_quota"] == "RPD"

    # Immediate Window Horizon
    assert "immediate_questions_conservative" in data
    assert "immediate_questions_typical" in data
    assert "immediate_questions_optimistic" in data
    assert data["immediate_limiting_quota"] in ["RPM", "TPM"]

    # Resource Metrics
    assert "remaining_requests_today" in data
    assert "rolling_requests_remaining" in data
    assert "rolling_tokens_remaining" in data
    assert "average_prompt_tokens" in data
    assert "average_completion_tokens" in data
    assert "average_total_tokens" in data
    assert "sample_size" in data
    assert "confidence" in data
    assert data["remaining_tokens_today"] is None

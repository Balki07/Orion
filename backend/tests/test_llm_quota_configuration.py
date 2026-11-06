"""
Test suite for Phase 2: Gemini Quota Configuration & Calculations.
Validates:
- Default quota initialization for gemini-3.5-flash-lite.
- Additive LLMQuotaConfig model persistence.
- GET and PUT /api/v1/settings/llm-quota API endpoints.
- Quota validation rules: negative limits, invalid timezones, invalid threshold percentages.
- Rolling 60s and timezone-aware daily usage calculations from LLMUsageRecords.
- Exclusion of deterministic fallback and cache hits from provider generation counts.
- Unknown token counts handled cleanly without fabrication.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4
import pytest
from conftest import TestSessionLocal

from app.models.llm_quota import LLMQuotaConfig
from app.models.llm_usage import LLMUsageRecord
from app.services.generation.quota_service import (
    get_daily_quota_boundary_utc,
    get_or_create_quota_config,
    get_quota_status,
    update_quota_config,
)


@pytest.mark.asyncio
async def test_default_quota_config_initialization():
    """Verify default reference values match user specifications for gemini-3.5-flash-lite."""
    async with TestSessionLocal() as session:
        unique_model = f"test-init-{uuid4().hex[:6]}"
        config = await get_or_create_quota_config(session, model_id=unique_model)
        assert config is not None
        assert config.model_id == unique_model
        assert config.rpm_limit == 15
        assert config.tpm_limit == 250000
        assert config.rpd_limit == 500
        assert config.warning_threshold_percent == 0.80
        assert config.safety_margin_percent == 0.10
        assert config.quota_timezone == "America/Los_Angeles"


def test_timezone_daily_boundary_calculation():
    """Verify UTC boundary calculation respects America/Los_Angeles midnight."""
    boundary = get_daily_quota_boundary_utc("America/Los_Angeles")
    assert boundary.tzinfo == timezone.utc
    assert boundary <= datetime.now(timezone.utc)
    # The boundary must be at most 24 hours ago
    assert (datetime.now(timezone.utc) - boundary).total_seconds() < 86400


@pytest.mark.asyncio
async def test_quota_service_usage_aggregation():
    """Verify rolling 60s and daily usage aggregations compute accurately."""
    test_model = f"test-agg-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with TestSessionLocal() as session:
        await get_or_create_quota_config(session, model_id=test_model)

        # 1. Recent successful provider call (within 60s)
        rec1 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id=f"trc-{uuid4().hex[:8]}",
            model=test_model,
            call_type="research_qa",
            is_provider_call=True,
            status="success",
            prompt_tokens=150,
            completion_tokens=50,
            total_tokens=200,
            created_at=now - timedelta(seconds=15),
        )
        # 2. Call from earlier today (outside 60s, inside today's quota window)
        today_start = get_daily_quota_boundary_utc("America/Los_Angeles")
        rec2_time = today_start + timedelta(minutes=1) if (now - today_start) > timedelta(seconds=70) else (now - timedelta(seconds=90))
        rec2 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id=f"trc-{uuid4().hex[:8]}",
            model=test_model,
            call_type="research_qa",
            is_provider_call=True,
            status="success",
            prompt_tokens=300,
            completion_tokens=100,
            total_tokens=400,
            created_at=rec2_time,
        )
        # 3. Failed provider attempt within 60s
        rec3 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id=f"trc-{uuid4().hex[:8]}",
            model=test_model,
            call_type="research_qa",
            is_provider_call=True,
            status="failed",
            error_category="RESOURCE_EXHAUSTED",
            http_status_code=429,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            created_at=now - timedelta(seconds=10),
        )
        # 4. Deterministic fallback (should NOT count toward provider attempts)
        rec4 = LLMUsageRecord(
            request_id=f"req-{uuid4().hex[:8]}",
            trace_id=f"trc-{uuid4().hex[:8]}",
            model=test_model,
            call_type="research_qa",
            is_provider_call=False,
            status="fallback",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            created_at=now - timedelta(seconds=5),
        )

        session.add_all([rec1, rec2, rec3, rec4])
        await session.commit()

        status = await get_quota_status(session, model_id=test_model)

        # Rolling window (last 60s): rec1 and rec3 are provider calls = 2 attempts. rec1 has 200 tokens.
        assert status.rolling_usage.rolling_60s_requests == 2
        assert status.rolling_usage.rolling_60s_tokens == 200

        # Daily window: rec1, rec2, rec3 are provider calls = 3 attempts total (2 success, 1 failed)
        assert status.daily_usage.successful_generations_today == 2
        assert status.daily_usage.failed_provider_attempts_today == 1
        assert status.daily_usage.total_provider_attempts_today == 3
        assert status.daily_usage.total_tokens_today == 600
        assert status.daily_usage.prompt_tokens_today == 450
        assert status.daily_usage.completion_tokens_today == 150


@pytest.mark.asyncio
async def test_api_get_llm_quota(client):
    """GET /api/v1/settings/llm-quota returns active model configuration and usage."""
    resp = await client.get("/api/v1/settings/llm-quota")
    assert resp.status_code == 200
    data = resp.json()

    assert "model_id" in data
    assert "rpm_limit" in data
    assert "tpm_limit" in data
    assert "rpd_limit" in data
    assert "rolling_usage" in data
    assert "daily_usage" in data
    assert "quota_source_disclaimer" in data
    assert "Google AI Studio" in data["quota_source_disclaimer"]

    assert data["rpm_limit"] > 0
    assert data["tpm_limit"] > 0
    assert data["rpd_limit"] > 0
    assert data["quota_timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_api_put_llm_quota_update(client):
    """PUT /api/v1/settings/llm-quota updates reference limits accurately for authorized admin."""
    admin_headers = {"X-User-Id": "user_admin_001"}
    update_payload = {
        "rpm_limit": 20,
        "tpm_limit": 300000,
        "rpd_limit": 600,
        "warning_threshold_percent": 0.85,
        "safety_margin_percent": 0.15,
        "quota_timezone": "America/Los_Angeles",
    }
    resp = await client.put("/api/v1/settings/llm-quota", json=update_payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["rpm_limit"] == 20
    assert data["tpm_limit"] == 300000
    assert data["rpd_limit"] == 600
    assert data["warning_threshold_percent"] == 0.85
    assert data["safety_margin_percent"] == 0.15

    # Re-fetch with GET to confirm persistence
    get_resp = await client.get("/api/v1/settings/llm-quota")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["rpm_limit"] == 20
    assert get_data["tpm_limit"] == 300000


@pytest.mark.asyncio
async def test_api_put_llm_quota_validation_errors(client):
    """PUT /api/v1/settings/llm-quota rejects negative limits and invalid timezones."""
    admin_headers = {"X-User-Id": "user_admin_001"}
    # 1. Negative RPM
    bad_rpm = {
        "rpm_limit": -5,
        "tpm_limit": 250000,
        "rpd_limit": 500,
        "warning_threshold_percent": 0.80,
        "safety_margin_percent": 0.10,
        "quota_timezone": "America/Los_Angeles",
    }
    resp = await client.put("/api/v1/settings/llm-quota", json=bad_rpm, headers=admin_headers)
    assert resp.status_code == 422

    # 2. Invalid timezone
    bad_tz = {
        "rpm_limit": 15,
        "tpm_limit": 250000,
        "rpd_limit": 500,
        "warning_threshold_percent": 0.80,
        "safety_margin_percent": 0.10,
        "quota_timezone": "Invalid/Fake_Zone",
    }
    resp = await client.put("/api/v1/settings/llm-quota", json=bad_tz, headers=admin_headers)
    assert resp.status_code == 422

    # 3. Threshold > 1.0
    bad_thresh = {
        "rpm_limit": 15,
        "tpm_limit": 250000,
        "rpd_limit": 500,
        "warning_threshold_percent": 1.5,
        "safety_margin_percent": 0.10,
        "quota_timezone": "America/Los_Angeles",
    }
    resp = await client.put("/api/v1/settings/llm-quota", json=bad_thresh, headers=admin_headers)
    assert resp.status_code == 422

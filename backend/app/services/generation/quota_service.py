"""LLM Quota Management Service.

Calculates rolling RPM/TPM utilization, daily RPD utilization using timezone boundaries,
and manages persistent model quota configurations.
"""

import math
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.llm_quota import LLMQuotaConfig
from app.models.llm_usage import LLMUsageRecord
from app.schemas.llm_quota import (
    LLMDailyUsage,
    LLMQuestionBudgetEstimate,
    LLMQuotaConfigUpdate,
    LLMQuotaResponse,
    LLMRollingUsage,
)

# Reference defaults matching Google AI Studio tier for gemini-3.5-flash-lite
DEFAULT_RPM = 15
DEFAULT_TPM = 250000
DEFAULT_RPD = 500
DEFAULT_TIMEZONE = "America/Los_Angeles"
DEFAULT_WARNING_THRESHOLD = 0.80
DEFAULT_SAFETY_MARGIN = 0.10


def get_daily_quota_boundary_utc(quota_timezone: str) -> datetime:
    """Calculate the UTC start timestamp for today's quota window in the given timezone.

    Google AI Studio resets daily quotas at midnight Pacific Time.
    This function converts midnight in `quota_timezone` to a UTC datetime for DB queries.
    """
    try:
        tz = ZoneInfo(quota_timezone.strip())
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    now_in_tz = datetime.now(tz)
    midnight_in_tz = now_in_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_in_tz.astimezone(UTC)


async def get_or_create_quota_config(
    db: AsyncSession,
    model_id: str | None = None,
) -> LLMQuotaConfig:
    """Retrieve existing quota configuration for the model, or insert defaults if not present."""
    target_model = model_id or settings.GEMINI_MODEL

    stmt = select(LLMQuotaConfig).where(LLMQuotaConfig.model_id == target_model)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if config is None:
        config = LLMQuotaConfig(
            model_id=target_model,
            rpm_limit=DEFAULT_RPM,
            tpm_limit=DEFAULT_TPM,
            rpd_limit=DEFAULT_RPD,
            quota_timezone=DEFAULT_TIMEZONE,
            warning_threshold_percent=DEFAULT_WARNING_THRESHOLD,
            safety_margin_percent=DEFAULT_SAFETY_MARGIN,
            updated_at=datetime.now(UTC),
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return config


async def get_quota_status(
    db: AsyncSession,
    model_id: str | None = None,
) -> LLMQuotaResponse:
    """Calculate rolling 60-second usage, daily usage, and return the full quota status."""
    target_model = model_id or settings.GEMINI_MODEL
    config = await get_or_create_quota_config(db, target_model)

    today_start_utc = get_daily_quota_boundary_utc(config.quota_timezone)
    rolling_cutoff_utc = datetime.now(UTC) - timedelta(seconds=60)

    # 1. Daily Aggregations (from today_start_utc to now)
    daily_stmt = select(
        func.count(LLMUsageRecord.id).label("total_records"),
        func.count(func.distinct(LLMUsageRecord.trace_id)).label("unique_questions"),
        func.sum(
            case((LLMUsageRecord.is_provider_call.is_(True), 1), else_=0)
        ).label("provider_calls"),
        func.sum(
            case(
                ((LLMUsageRecord.is_provider_call.is_(True)) & (LLMUsageRecord.status == "success"), 1),
                else_=0,
            )
        ).label("successful_generations"),
        func.sum(
            case(
                ((LLMUsageRecord.is_provider_call.is_(True)) & (LLMUsageRecord.status == "failed"), 1),
                else_=0,
            )
        ).label("failed_provider_attempts"),
        func.sum(
            case(
                (LLMUsageRecord.is_provider_call.is_(False), 1),
                else_=0,
            )
        ).label("fallback_events"),
        func.coalesce(func.sum(LLMUsageRecord.prompt_tokens), 0).label("prompt_tokens"),
        func.coalesce(func.sum(LLMUsageRecord.completion_tokens), 0).label("completion_tokens"),
        func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0).label("total_tokens"),
    ).where(
        LLMUsageRecord.model == target_model,
        LLMUsageRecord.created_at >= today_start_utc,
    )

    daily_res = await db.execute(daily_stmt)
    d_row = daily_res.one()

    total_attempts_today = int(d_row.provider_calls or 0)
    successful_today = int(d_row.successful_generations or 0)
    failed_today = int(d_row.failed_provider_attempts or 0)
    fallback_today = int(d_row.fallback_events or 0)
    unique_questions_today = int(d_row.unique_questions or 0)
    prompt_tokens_today = int(d_row.prompt_tokens or 0)
    completion_tokens_today = int(d_row.completion_tokens or 0)
    total_tokens_today = int(d_row.total_tokens or 0)

    rpd_utilization = (
        round((total_attempts_today / config.rpd_limit) * 100.0, 2)
        if config.rpd_limit > 0
        else 0.0
    )

    daily_usage = LLMDailyUsage(
        quota_timezone=config.quota_timezone,
        today_start_utc=today_start_utc,
        unique_questions_today=unique_questions_today,
        total_provider_attempts_today=total_attempts_today,
        successful_generations_today=successful_today,
        failed_provider_attempts_today=failed_today,
        fallback_events_today=fallback_today,
        prompt_tokens_today=prompt_tokens_today,
        completion_tokens_today=completion_tokens_today,
        total_tokens_today=total_tokens_today,
        rpd_limit=config.rpd_limit,
        rpd_utilization_percent=rpd_utilization,
    )

    # 2. Rolling 60-Second Aggregations
    rolling_stmt = select(
        func.count(LLMUsageRecord.id).label("rolling_requests"),
        func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0).label("rolling_tokens"),
    ).where(
        LLMUsageRecord.model == target_model,
        LLMUsageRecord.is_provider_call.is_(True),
        LLMUsageRecord.created_at >= rolling_cutoff_utc,
    )

    rolling_res = await db.execute(rolling_stmt)
    r_row = rolling_res.one()

    rolling_requests = int(r_row.rolling_requests or 0)
    rolling_tokens = int(r_row.rolling_tokens or 0)

    rpm_utilization = (
        round((rolling_requests / config.rpm_limit) * 100.0, 2)
        if config.rpm_limit > 0
        else 0.0
    )
    tpm_utilization = (
        round((rolling_tokens / config.tpm_limit) * 100.0, 2)
        if config.tpm_limit > 0
        else 0.0
    )

    rolling_usage = LLMRollingUsage(
        rolling_60s_requests=rolling_requests,
        rolling_60s_tokens=rolling_tokens,
        rpm_limit=config.rpm_limit,
        tpm_limit=config.tpm_limit,
        rpm_utilization_percent=rpm_utilization,
        tpm_utilization_percent=tpm_utilization,
    )

    is_active = (target_model == settings.GEMINI_MODEL)

    return LLMQuotaResponse(
        model_id=target_model,
        is_active_model=is_active,
        is_reference_quota=True,
        rpm_limit=config.rpm_limit,
        tpm_limit=config.tpm_limit,
        rpd_limit=config.rpd_limit,
        quota_timezone=config.quota_timezone,
        warning_threshold_percent=config.warning_threshold_percent,
        safety_margin_percent=config.safety_margin_percent,
        last_updated_at=config.updated_at,
        rolling_usage=rolling_usage,
        daily_usage=daily_usage,
    )


async def update_quota_config(
    db: AsyncSession,
    updates: LLMQuotaConfigUpdate,
    model_id: str | None = None,
) -> LLMQuotaResponse:
    """Update configured reference limits for an LLM model."""
    target_model = model_id or settings.GEMINI_MODEL
    config = await get_or_create_quota_config(db, target_model)

    config.rpm_limit = updates.rpm_limit
    config.tpm_limit = updates.tpm_limit
    config.rpd_limit = updates.rpd_limit
    config.quota_timezone = updates.quota_timezone.strip()
    config.warning_threshold_percent = updates.warning_threshold_percent
    config.safety_margin_percent = updates.safety_margin_percent
    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return await get_quota_status(db, target_model)


async def get_question_budget_estimate(
    db: AsyncSession,
    model_id: str | None = None,
) -> LLMQuestionBudgetEstimate:
    """Calculate remaining question budget and quota limit projections.

    Respects RPD, RPM, and TPM constraints with safety reserve margins applied.
    Differentiates multi-attempt retries from single research questions and uses
    conservative fallbacks when historical usage sample is low.
    """
    target_model = model_id or settings.GEMINI_MODEL
    status = await get_quota_status(db, target_model)

    # 1. Query token consumption statistics from successful generations with usage metadata
    token_stmt = select(
        func.count(LLMUsageRecord.id).label("sample_size"),
        func.avg(LLMUsageRecord.prompt_tokens).label("avg_prompt"),
        func.avg(LLMUsageRecord.completion_tokens).label("avg_completion"),
        func.avg(LLMUsageRecord.total_tokens).label("avg_total"),
    ).where(
        LLMUsageRecord.model == target_model,
        LLMUsageRecord.is_provider_call.is_(True),
        LLMUsageRecord.status == "success",
        LLMUsageRecord.has_usage_metadata.is_(True),
        LLMUsageRecord.total_tokens.is_not(None),
    )
    token_res = await db.execute(token_stmt)
    t_row = token_res.one()

    sample_size = int(t_row.sample_size or 0)

    # Conservative default token assumptions for RAG research Q&A
    DEFAULT_PROMPT_TOKENS = 3500
    DEFAULT_COMPLETION_TOKENS = 1800
    DEFAULT_TOTAL_TOKENS = 5300

    if sample_size < 5:
        confidence = "low"
        is_fallback = True
        avg_prompt = int(round(float(t_row.avg_prompt))) if t_row.avg_prompt is not None else DEFAULT_PROMPT_TOKENS
        avg_completion = int(round(float(t_row.avg_completion))) if t_row.avg_completion is not None else DEFAULT_COMPLETION_TOKENS
        avg_total = int(round(float(t_row.avg_total))) if t_row.avg_total is not None else DEFAULT_TOTAL_TOKENS
        disclaimer = (
            f"Preliminary budget projection based on conservative baseline estimates (low sample size: {sample_size} recorded). "
            "Estimates will automatically refine as more questions are processed. External project usage is not tracked."
        )
    else:
        confidence = "high" if sample_size >= 20 else "medium"
        is_fallback = False
        avg_prompt = int(round(float(t_row.avg_prompt)))
        avg_completion = int(round(float(t_row.avg_completion)))
        avg_total = int(round(float(t_row.avg_total)))
        disclaimer = (
            f"Dynamic budget projection calculated from {sample_size} real grounded generations. "
            "Estimates reflect ORION local usage and applied safety reserve margins."
        )

    # 2. Historical Retry Factor (attempts per question)
    # Exclude deterministic fallback, zero-context abstention, and cache hits (is_provider_call=True only)
    attempt_stmt = select(
        func.count(LLMUsageRecord.id).label("total_provider_calls"),
        func.count(func.distinct(LLMUsageRecord.trace_id)).label("unique_questions"),
    ).where(
        LLMUsageRecord.model == target_model,
        LLMUsageRecord.is_provider_call.is_(True),
    )
    attempt_res = await db.execute(attempt_stmt)
    a_row = attempt_res.one()

    total_provider_calls = int(a_row.total_provider_calls or 0)
    unique_questions = int(a_row.unique_questions or 0)

    if unique_questions > 0 and total_provider_calls > 0:
        base_attempts_per_q = total_provider_calls / unique_questions
    else:
        base_attempts_per_q = 1.0

    typical_attempts = max(1.0, round(base_attempts_per_q, 2))
    conservative_attempts = max(1.15, round(base_attempts_per_q * 1.15, 2))
    optimistic_attempts = 1.0

    # 3. Token distributions (conservative / typical / optimistic)
    typical_tokens = max(1, avg_total)
    conservative_tokens = max(typical_tokens, int(round(typical_tokens * 1.25)))
    optimistic_tokens = max(1000, int(round(typical_tokens * 0.80)))

    # 4. Usable capacities after safety margin
    # Safety margin applies to the raw quota limit: usable_limit = floor(limit * (1.0 - margin))
    margin = status.safety_margin_percent
    usable_rpd = int(math.floor(status.rpd_limit * (1.0 - margin)))
    usable_rpm = int(math.floor(status.rpm_limit * (1.0 - margin)))
    usable_tpm = int(math.floor(status.tpm_limit * (1.0 - margin)))

    remaining_requests_today = max(0, usable_rpd - status.daily_usage.total_provider_attempts_today)
    rolling_requests_remaining = max(0, usable_rpm - status.rolling_usage.rolling_60s_requests)
    rolling_tokens_remaining = max(0, usable_tpm - status.rolling_usage.rolling_60s_tokens)

    # 5. Daily Horizon Question Budget (strictly governed by RPD and attempt ratios)
    # A low RPM or TPM does NOT reduce the daily capacity over the 24-hour quota window
    daily_questions_cons = int(remaining_requests_today // conservative_attempts)
    daily_questions_typ = int(remaining_requests_today // typical_attempts)
    daily_questions_opt = int(remaining_requests_today // optimistic_attempts)
    daily_limiting_quota = "RPD"

    # 6. Immediate Window Question Capacity (rolling 60-second RPM and TPM limits)
    # Determines what can be submitted right now in the active rolling-minute window
    rpm_questions_cons = int(rolling_requests_remaining // conservative_attempts)
    rpm_questions_typ = int(rolling_requests_remaining // typical_attempts)
    rpm_questions_opt = int(rolling_requests_remaining // optimistic_attempts)

    tpm_questions_cons = int(rolling_tokens_remaining // conservative_tokens) if conservative_tokens > 0 else 0
    tpm_questions_typ = int(rolling_tokens_remaining // typical_tokens) if typical_tokens > 0 else 0
    tpm_questions_opt = int(rolling_tokens_remaining // optimistic_tokens) if optimistic_tokens > 0 else 0

    if rpm_questions_cons <= tpm_questions_cons:
        immediate_limiting_quota = "RPM"
    else:
        immediate_limiting_quota = "TPM"

    immediate_questions_cons = min(rpm_questions_cons, tpm_questions_cons)
    immediate_questions_typ = min(rpm_questions_typ, tpm_questions_typ)
    immediate_questions_opt = min(rpm_questions_opt, tpm_questions_opt)

    return LLMQuestionBudgetEstimate(
        model_id=target_model,
        is_active_model=status.is_active_model,
        # --- Daily Horizon ---
        daily_questions_remaining=daily_questions_cons,
        daily_questions_typical=daily_questions_typ,
        daily_questions_optimistic=daily_questions_opt,
        daily_limiting_quota=daily_limiting_quota,
        # --- Immediate Window Horizon ---
        immediate_questions_conservative=immediate_questions_cons,
        immediate_questions_typical=immediate_questions_typ,
        immediate_questions_optimistic=immediate_questions_opt,
        immediate_limiting_quota=immediate_limiting_quota,
        # --- Compatibility Aliases ---
        estimated_questions_remaining=daily_questions_cons,
        estimated_questions_typical=daily_questions_typ,
        estimated_questions_optimistic=daily_questions_opt,
        limiting_quota=daily_limiting_quota,
        rolling_questions_remaining=immediate_questions_cons,
        # --- Resource Breakdown ---
        remaining_requests_today=remaining_requests_today,
        remaining_tokens_today=None,
        rolling_requests_remaining=rolling_requests_remaining,
        rolling_tokens_remaining=rolling_tokens_remaining,
        average_prompt_tokens=avg_prompt,
        average_completion_tokens=avg_completion,
        average_total_tokens=avg_total,
        attempts_per_question=typical_attempts,
        sample_size=sample_size,
        confidence=confidence,
        is_fallback_estimate=is_fallback,
        safety_margin_percent=status.safety_margin_percent,
        estimation_disclaimer=disclaimer,
    )


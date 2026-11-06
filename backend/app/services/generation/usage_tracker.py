"""LLM Usage Tracker Service.

Records every LLM interaction, provider API call, retry, and fallback to persistent storage.
Guarantees UTC timestamps, zero credential/prompt leakage, and isolated transaction safety.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.llm_usage import LLMUsageRecord


async def record_llm_usage(
    *,
    trace_id: str | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    call_type: str = "research_qa",
    model: str,
    attempt_number: int = 1,
    max_attempts: int = 3,
    is_provider_call: bool = True,
    status: str,  # "success" | "failed" | "fallback" | "abstained_no_context" | "cached"
    http_status_code: int | None = None,
    error_category: str | None = None,
    error_detail: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    has_usage_metadata: bool = False,
    latency_ms: float = 0.0,
    created_at: datetime | None = None,
    db: AsyncSession | None = None,
) -> LLMUsageRecord | None:
    """Record an LLM generation attempt or fallback event to persistent database storage."""
    record = LLMUsageRecord(
        trace_id=trace_id,
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        call_type=call_type,
        model=model,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        is_provider_call=is_provider_call,
        status=status,
        http_status_code=http_status_code,
        error_category=error_category,
        error_detail=error_detail[:1000] if error_detail else None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        has_usage_metadata=has_usage_metadata,
        latency_ms=round(max(0.0, latency_ms), 2),
        created_at=created_at or datetime.now(UTC),
    )

    try:
        if db is not None:
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return record
        else:
            async with AsyncSessionLocal() as session:
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record
    except Exception as err:
        logger.error(f"Failed to persist LLMUsageRecord: {err}", exc_info=True)
        return None


async def get_recent_usage_records(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    model: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[LLMUsageRecord]:
    """Retrieve recent usage records sorted newest to oldest."""
    stmt = select(LLMUsageRecord)
    if user_id:
        stmt = stmt.where(LLMUsageRecord.user_id == user_id)
    if model:
        stmt = stmt.where(LLMUsageRecord.model == model)
    stmt = stmt.order_by(desc(LLMUsageRecord.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_usage_summary(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    model: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    """Calculate aggregated metrics over a specific time window."""
    stmt = select(
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
        ).label("successful_provider_calls"),
        func.sum(
            case(
                ((LLMUsageRecord.is_provider_call.is_(True)) & (LLMUsageRecord.status == "failed"), 1),
                else_=0,
            )
        ).label("failed_provider_calls"),
        func.sum(
            case(
                (LLMUsageRecord.status == "fallback", 1),
                else_=0,
            )
        ).label("fallback_calls"),
        func.coalesce(func.sum(LLMUsageRecord.prompt_tokens), 0).label("total_prompt_tokens"),
        func.coalesce(func.sum(LLMUsageRecord.completion_tokens), 0).label("total_completion_tokens"),
        func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.avg(LLMUsageRecord.latency_ms), 0.0).label("avg_latency_ms"),
    )

    if user_id:
        stmt = stmt.where(LLMUsageRecord.user_id == user_id)
    if model:
        stmt = stmt.where(LLMUsageRecord.model == model)
    if start_time:
        stmt = stmt.where(LLMUsageRecord.created_at >= start_time)
    if end_time:
        stmt = stmt.where(LLMUsageRecord.created_at <= end_time)

    res = await db.execute(stmt)
    row = res.one()

    return {
        "total_records": row.total_records or 0,
        "unique_questions": row.unique_questions or 0,
        "provider_calls": row.provider_calls or 0,
        "successful_provider_calls": row.successful_provider_calls or 0,
        "failed_provider_calls": row.failed_provider_calls or 0,
        "fallback_calls": row.fallback_calls or 0,
        "total_prompt_tokens": int(row.total_prompt_tokens or 0),
        "total_completion_tokens": int(row.total_completion_tokens or 0),
        "total_tokens": int(row.total_tokens or 0),
        "avg_latency_ms": round(float(row.avg_latency_ms or 0.0), 2),
    }


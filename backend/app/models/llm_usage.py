"""LLM Usage and Provider Generation Record ORM models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid


class LLMUsageRecord(Base):
    """Persistent audit log of every LLM interaction, provider API call, retry, and fallback.

    Accounting Guarantees:
    - Every actual Gemini network attempt has is_provider_call=True.
    - Deterministic fallbacks, zero-context abstentions, and cache hits have is_provider_call=False.
    - Multiple retries for the same question share the same trace_id but have distinct attempt_numbers.
    - Token counts are exact integers when returned by provider usage metadata, or None if omitted.
    - Timestamps are strictly UTC.
    - Full prompts, document excerpts, and API keys are NEVER stored.
    """

    __tablename__ = "llm_usage_records"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("llm_use"),
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    call_type: Mapped[str] = mapped_column(String(32), default="research_qa", nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_provider_call: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # "success" | "failed" | "fallback" | "abstained_no_context" | "cached"
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_usage_metadata: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )


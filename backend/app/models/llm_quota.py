"""LLM Quota Configuration ORM model."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMQuotaConfig(Base):
    """Configured reference limits for an LLM provider model.

    DISCLOSURE:
    These are local reference/configured limits, NOT guaranteed real-time
    remaining account limits from Google. External apps or keys sharing the same
    Google Cloud/AI Studio project can consume quota without appearing in ORION's
    local usage database.
    """

    __tablename__ = "llm_quota_configs"

    model_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    tpm_limit: Mapped[int] = mapped_column(Integer, default=250000, nullable=False)
    rpd_limit: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    quota_timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles", nullable=False)
    warning_threshold_percent: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)
    safety_margin_percent: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    notes: Mapped[str] = mapped_column(
        Text,
        default="Reference limits based on Google AI Studio tier. External project usage may consume quota independently.",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


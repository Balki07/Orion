"""Authentication and Login Audit Event ORM models."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class AuthAuditEvent(Base, TimestampMixin):
    """Persistent audit log of authentication and login events for administrator oversight.

    Security & Privacy Guarantees:
    - PASSWORDS, SESSION TOKENS, AND SECRETS ARE NEVER RECORDED.
    - Only safe audit metadata (event type, success status, sanitized failure reason, masked IP/UA) is retained.
    """

    __tablename__ = "auth_audit_events"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("evt"),
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )  # "login_success", "login_failure", "logout", "register"
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_auth_events_user_time", "user_id", "created_at"),
        Index("ix_auth_events_type_time", "event_type", "created_at"),
        Index("ix_auth_events_actor_time", "actor_id", "created_at"),
    )


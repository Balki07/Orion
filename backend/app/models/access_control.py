"""Access Request and Invitation ORM models for Strict Role-Based Functionality Control."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class AccessRequest(Base, TimestampMixin):
    """User-submitted research access requests requiring administrator review."""

    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("req"),
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    research_purpose: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    intended_data_types: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )  # "pending", "approved", "rejected"
    reviewed_by: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="access_requests",
    )
    reviewer: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
    invitation: Mapped["Invitation | None"] = relationship(
        "Invitation",
        back_populates="access_request",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_access_requests_user_status", "user_id", "status"),
    )


class Invitation(Base, TimestampMixin):
    """One-time cryptographic invitations issued by administrators for researcher access."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("inv"),
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_request_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("access_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    is_redeemed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="invitations",
    )
    access_request: Mapped["AccessRequest | None"] = relationship(
        "AccessRequest",
        back_populates="invitation",
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )

    __table_args__ = (
        Index("ix_invitations_lookup", "user_id", "is_redeemed", "expires_at"),
    )


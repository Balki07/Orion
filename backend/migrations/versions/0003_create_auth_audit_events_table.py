"""Create authentication and login audit events table

Revision ID: 0003_auth_audit_events
Revises: 0002_research_domain
Create Date: 2026-11-05 10:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_auth_audit_events"
down_revision: str | None = "0002_research_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"])
    op.create_index("ix_auth_audit_events_email", "auth_audit_events", ["email"])
    op.create_index("ix_auth_audit_events_event_type", "auth_audit_events", ["event_type"])
    op.create_index("ix_auth_audit_events_success", "auth_audit_events", ["success"])
    op.create_index("ix_auth_events_user_time", "auth_audit_events", ["user_id", "created_at"])
    op.create_index("ix_auth_events_type_time", "auth_audit_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_table("auth_audit_events")


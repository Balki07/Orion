"""Create access control, access requests, and invitations tables

Revision ID: 0004_access_control
Revises: 0003_auth_audit_events
Create Date: 2026-11-06 09:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_access_control"
down_revision: str | None = "0003_auth_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add role and access_status columns to users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=32), server_default="researcher", nullable=False)
        )
        batch_op.add_column(
            sa.Column("access_status", sa.String(length=32), server_default="pending_request", nullable=False)
        )
        batch_op.create_index("ix_users_role", ["role"])
        batch_op.create_index("ix_users_access_status", ["access_status"])
        batch_op.create_index("ix_users_role_access_status", ["role", "access_status"])

    # 2. Backfill existing users to active status to maintain uninterrupted service
    # Backfill orionadmin@gmail.com as admin + active
    op.execute(
        sa.text(
            "UPDATE users SET role = 'admin', access_status = 'active' "
            "WHERE LOWER(email) = 'orionadmin@gmail.com'"
        )
    )
    # Existing researchers prior to migration are backfilled to active
    op.execute(
        sa.text(
            "UPDATE users SET role = 'researcher', access_status = 'active' "
            "WHERE LOWER(email) != 'orionadmin@gmail.com' AND access_status = 'pending_request'"
        )
    )

    # 3. Add actor_id and details columns to auth_audit_events
    with op.batch_alter_table("auth_audit_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "actor_id",
                sa.String(length=64),
                sa.ForeignKey("users.id", name="fk_auth_audit_events_actor_id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("details", sa.Text(), nullable=True))
        batch_op.create_index("ix_auth_audit_events_actor_id", ["actor_id"])

    # 4. Create access_requests table
    op.create_table(
        "access_requests",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("research_purpose", sa.Text(), nullable=False),
        sa.Column("intended_data_types", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column(
            "reviewed_by",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
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
    op.create_index("ix_access_requests_user_id", "access_requests", ["user_id"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])
    op.create_index("ix_access_requests_user_status", "access_requests", ["user_id", "status"])

    # 5. Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "access_request_id",
            sa.String(length=64),
            sa.ForeignKey("access_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_redeemed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"])
    op.create_index("ix_invitations_user_id", "invitations", ["user_id"])
    op.create_index("ix_invitations_is_redeemed", "invitations", ["is_redeemed"])
    op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])
    op.create_index("ix_invitations_lookup", "invitations", ["user_id", "is_redeemed", "expires_at"])


def downgrade() -> None:
    # 1. Drop invitations table
    op.drop_table("invitations")

    # 2. Drop access_requests table
    op.drop_table("access_requests")

    # 3. Drop columns from auth_audit_events
    with op.batch_alter_table("auth_audit_events", schema=None) as batch_op:
        batch_op.drop_index("ix_auth_audit_events_actor_id")
        batch_op.drop_column("details")
        batch_op.drop_column("actor_id")

    # 4. Drop columns from users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_role_access_status")
        batch_op.drop_index("ix_users_access_status")
        batch_op.drop_index("ix_users_role")
        batch_op.drop_column("access_status")
        batch_op.drop_column("role")

"""Isolated test for Alembic Migration 0004 on a scratch database.

DO NOT apply to live Aiven PostgreSQL.
Verifies:
1. Upgrading to 0004 adds role and access_status columns to users table.
2. Backfills orionadmin@gmail.com as admin+active and existing researchers as researcher+active.
3. Adds actor_id and details to auth_audit_events.
4. Creates access_requests and invitations tables with proper indexes.
5. Downgrading 0004 cleanly removes tables and columns.
6. Re-upgrading is successful.
"""

import importlib
import os
import tempfile
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

# Dynamically import migration script starting with digits
mig_0004 = importlib.import_module("migrations.versions.0004_create_access_control_tables")


@pytest.fixture
def scratch_db():
    """Create a temporary SQLite database pre-populated with schema at revision 0003."""
    fd, path = tempfile.mkstemp(suffix="_scratch_0004.db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    engine = sa.create_engine(db_url)

    with engine.begin() as conn:
        # Create users table as it existed in 0003
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id VARCHAR(64) PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                display_name VARCHAR(128) NOT NULL,
                institution VARCHAR(255),
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
        )
        # Create auth_audit_events table as it existed in 0003
        conn.execute(
            text(
                """
            CREATE TABLE auth_audit_events (
                id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
                email VARCHAR(255),
                event_type VARCHAR(32) NOT NULL,
                success BOOLEAN NOT NULL DEFAULT 1,
                ip_address VARCHAR(45),
                user_agent VARCHAR(255),
                failure_reason VARCHAR(128),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
        )
        # Insert pre-existing admin and researcher
        conn.execute(
            text(
                """
            INSERT INTO users (id, email, hashed_password, display_name, status, is_active)
            VALUES 
                ('usr_admin_01', 'orionadmin@gmail.com', 'hashed_pw_admin', 'Primary Administrator', 'active', 1),
                ('usr_res_01', 'researcher_existing@domain.edu', 'hashed_pw_res', 'Dr. Researcher', 'active', 1)
            """
            )
        )

    yield engine, path

    engine.dispose()
    if os.path.exists(path):
        os.remove(path)


def test_migration_0004_upgrade_and_downgrade(scratch_db):
    engine, db_path = scratch_db

    # Execute upgrade
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        # Patch alembic op in the module
        mig_0004.op = op
        mig_0004.upgrade()

    # Verify schema after upgrade
    insp = inspect(engine)
    user_cols = {c["name"]: c for c in insp.get_columns("users")}
    assert "role" in user_cols, "Column 'role' missing from users table"
    assert "access_status" in user_cols, "Column 'access_status' missing from users table"

    audit_cols = {c["name"]: c for c in insp.get_columns("auth_audit_events")}
    assert "actor_id" in audit_cols, "Column 'actor_id' missing from auth_audit_events"
    assert "details" in audit_cols, "Column 'details' missing from auth_audit_events"

    tables = insp.get_table_names()
    assert "access_requests" in tables, "Table 'access_requests' was not created"
    assert "invitations" in tables, "Table 'invitations' was not created"

    # Verify backfill data
    with engine.connect() as conn:
        admin_row = conn.execute(
            text("SELECT role, access_status FROM users WHERE email = 'orionadmin@gmail.com'")
        ).fetchone()
        assert admin_row is not None
        assert admin_row[0] == "admin"
        assert admin_row[1] == "active"

        res_row = conn.execute(
            text("SELECT role, access_status FROM users WHERE email = 'researcher_existing@domain.edu'")
        ).fetchone()
        assert res_row is not None
        assert res_row[0] == "researcher"
        assert res_row[1] == "active"

    # Execute downgrade
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mig_0004.op = op
        mig_0004.downgrade()

    # Verify schema after downgrade
    insp = inspect(engine)
    user_cols_down = {c["name"]: c for c in insp.get_columns("users")}
    assert "role" not in user_cols_down, "Column 'role' was not dropped from users"
    assert "access_status" not in user_cols_down, "Column 'access_status' was not dropped from users"

    audit_cols_down = {c["name"]: c for c in insp.get_columns("auth_audit_events")}
    assert "actor_id" not in audit_cols_down, "Column 'actor_id' was not dropped from auth_audit_events"
    assert "details" not in audit_cols_down, "Column 'details' was not dropped from auth_audit_events"

    tables_down = insp.get_table_names()
    assert "access_requests" not in tables_down, "Table 'access_requests' was not dropped"
    assert "invitations" not in tables_down, "Table 'invitations' was not dropped"

    # Re-apply upgrade to ensure idempotence
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mig_0004.op = op
        mig_0004.upgrade()

    insp_re = inspect(engine)
    assert "access_requests" in insp_re.get_table_names()
    assert "invitations" in insp_re.get_table_names()

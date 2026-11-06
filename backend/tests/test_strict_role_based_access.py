"""Comprehensive integration test suite for ORION Strict Role-Based Functionality Control.

Covers:
1. Admin full platform access (research workspace + admin dashboard + platform settings)
2. Researcher own-account access (blocked from admin endpoints and other users' resources)
3. Pending / rejected / revoked users restricted with machine-readable HTTP 403 codes
4. End-to-end access request, approval, and cryptographic invitation redemption lifecycle
5. Anti-lockout safeguards protecting against administrator self-lockout or removing last admin
6. Background worker enforcement: aborts ingestion if document owner is revoked/unauthorized
"""

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.access_control import AccessRequest, Invitation
from app.models.document import Document
from app.models.user import User
from app.security.service import create_session_jwt, hash_password, hash_token
from app.security.state_machine import AccessStatus, PlatformRole
from app.services.ingestion.worker import DurableIngestionWorker


@pytest_asyncio.fixture
async def test_env():
    """Isolated SQLite test environment for access control validation."""
    fd, path = tempfile.mkstemp(suffix="_test_rbac.db")
    os.close(fd)
    db_url = f"sqlite+aiosqlite:///{path}"

    test_engine = create_async_engine(db_url, echo=False)
    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed users
    admin_id = "usr_admin_test_01"
    res_active_id = "usr_res_active_01"
    res_pending_id = "usr_res_pending_01"
    res_revoked_id = "usr_res_revoked_01"
    res_b_id = "usr_res_active_02"

    async with session_maker() as session:
        # 1. Primary Administrator
        admin = User(
            id=admin_id,
            email="orionadmin@gmail.com",
            hashed_password=hash_password("AdminSecurePassword123!"),
            display_name="Primary Admin",
            status="active",
            is_active=True,
            role=PlatformRole.ADMIN.value,
            access_status=AccessStatus.ACTIVE.value,
        )
        # 2. Active Researcher A
        res_a = User(
            id=res_active_id,
            email="researcher_a@domain.edu",
            hashed_password=hash_password("ResearcherPassword123!"),
            display_name="Dr. Researcher A",
            status="active",
            is_active=True,
            role=PlatformRole.RESEARCHER.value,
            access_status=AccessStatus.ACTIVE.value,
        )
        # 3. Active Researcher B
        res_b = User(
            id=res_b_id,
            email="researcher_b@domain.edu",
            hashed_password=hash_password("ResearcherPassword123!"),
            display_name="Dr. Researcher B",
            status="active",
            is_active=True,
            role=PlatformRole.RESEARCHER.value,
            access_status=AccessStatus.ACTIVE.value,
        )
        # 4. Pending Researcher
        res_pending = User(
            id=res_pending_id,
            email="researcher_pending@domain.edu",
            hashed_password=hash_password("PendingPassword123!"),
            display_name="Pending Researcher",
            status="active",
            is_active=True,
            role=PlatformRole.RESEARCHER.value,
            access_status=AccessStatus.PENDING_REQUEST.value,
        )
        # 5. Revoked Researcher
        res_revoked = User(
            id=res_revoked_id,
            email="researcher_revoked@domain.edu",
            hashed_password=hash_password("RevokedPassword123!"),
            display_name="Revoked Researcher",
            status="active",
            is_active=True,
            role=PlatformRole.RESEARCHER.value,
            access_status=AccessStatus.REVOKED.value,
        )
        session.add_all([admin, res_a, res_b, res_pending, res_revoked])

        # Add a document owned by Researcher B to test cross-tenant isolation
        doc_b = Document(
            id="doc_res_b_001",
            owner_id=res_b_id,
            filename="private_study_b.pdf",
            storage_key="docs/private_study_b.pdf",
            content_hash="hash_b_001",
            file_size=1024,
            page_count=5,
            status="completed",
        )
        session.add(doc_b)
        await session.commit()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Create session JWTs and sessions in DB
    async def create_user_client(user_id: str, email: str):
        from app.models.user import UserSession
        from datetime import UTC, datetime, timedelta

        sess_id = f"sess_{user_id}"
        token = create_session_jwt(user_id, email, sess_id)

        async with session_maker() as session:
            db_sess = UserSession(
                id=sess_id,
                user_id=user_id,
                session_token_hash=hash_token(sess_id),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
                is_revoked=False,
            )
            session.add(db_sess)
            await session.commit()

        transport = ASGITransport(app=app)
        client = AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        )
        return client

    clients = {
        "admin": await create_user_client(admin_id, "orionadmin@gmail.com"),
        "res_a": await create_user_client(res_active_id, "researcher_a@domain.edu"),
        "res_b": await create_user_client(res_b_id, "researcher_b@domain.edu"),
        "res_pending": await create_user_client(res_pending_id, "researcher_pending@domain.edu"),
        "res_revoked": await create_user_client(res_revoked_id, "researcher_revoked@domain.edu"),
        "anonymous": AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
    }

    yield {
        "engine": test_engine,
        "session_maker": session_maker,
        "clients": clients,
        "users": {
            "admin": admin_id,
            "res_a": res_active_id,
            "res_b": res_b_id,
            "res_pending": res_pending_id,
            "res_revoked": res_revoked_id,
        },
    }

    app.dependency_overrides.clear()
    for c in clients.values():
        await c.aclose()
    await test_engine.dispose()
    if os.path.exists(path):
        os.remove(path)


@pytest.mark.asyncio
async def test_admin_has_full_platform_access(test_env):
    """Admin must have unrestricted access to research workspace and admin management."""
    admin_client = test_env["clients"]["admin"]

    # 1. Research workspace endpoints accessible to admin
    docs_resp = await admin_client.get("/api/v1/documents")
    assert docs_resp.status_code == 200, f"Admin could not access documents: {docs_resp.text}"

    sessions_resp = await admin_client.get("/api/v1/research/sessions")
    assert sessions_resp.status_code == 200, f"Admin could not access research sessions: {sessions_resp.text}"

    notes_resp = await admin_client.get("/api/v1/notes")
    assert notes_resp.status_code == 200, f"Admin could not access notes: {notes_resp.text}"

    collections_resp = await admin_client.get("/api/v1/collections")
    assert collections_resp.status_code == 200, f"Admin could not access collections: {collections_resp.text}"

    usage_resp = await admin_client.get("/api/v1/usage")
    assert usage_resp.status_code == 200, f"Admin could not access usage: {usage_resp.text}"

    # 2. Admin dashboard endpoints accessible to admin
    overview_resp = await admin_client.get("/api/v1/admin/overview")
    assert overview_resp.status_code == 200, f"Admin could not access admin overview: {overview_resp.text}"

    users_resp = await admin_client.get("/api/v1/admin/users")
    assert users_resp.status_code == 200, f"Admin could not access user directory: {users_resp.text}"

    health_resp = await admin_client.get("/api/v1/admin/system-health")
    assert health_resp.status_code == 200, f"Admin could not access system health: {health_resp.text}"

    requests_resp = await admin_client.get("/api/v1/admin/access-requests")
    assert requests_resp.status_code == 200, f"Admin could not access access requests: {requests_resp.text}"


@pytest.mark.asyncio
async def test_researcher_restricted_from_admin_endpoints(test_env):
    """Approved researchers can access research workspace but are blocked from admin endpoints."""
    res_client = test_env["clients"]["res_a"]

    # 1. Can access own research workspace
    docs_resp = await res_client.get("/api/v1/documents")
    assert docs_resp.status_code == 200

    sessions_resp = await res_client.get("/api/v1/research/sessions")
    assert sessions_resp.status_code == 200

    # 2. Blocked from administrative endpoints
    admin_overview = await res_client.get("/api/v1/admin/overview")
    assert admin_overview.status_code == 403

    admin_users = await res_client.get("/api/v1/admin/users")
    assert admin_users.status_code == 403

    admin_requests = await res_client.get("/api/v1/admin/access-requests")
    assert admin_requests.status_code == 403

    admin_health = await res_client.get("/api/v1/admin/system-health")
    assert admin_health.status_code == 403

    quota_update = await res_client.put("/api/v1/settings/llm-quota", json={"rpm_limit": 100})
    assert quota_update.status_code == 403


@pytest.mark.asyncio
async def test_cross_researcher_data_isolation(test_env):
    """Researcher A cannot read Researcher B's documents or private resources."""
    res_a_client = test_env["clients"]["res_a"]

    # Attempt to access Document owned by Researcher B
    doc_resp = await res_a_client.get("/api/v1/documents/doc_res_b_001")
    assert doc_resp.status_code in (403, 404), f"Expected 403/404 for cross-user document access, got {doc_resp.status_code}"


@pytest.mark.asyncio
async def test_pending_and_revoked_users_receive_explicit_403(test_env):
    """Pending and revoked accounts can authenticate but are blocked from research operations."""
    pending_client = test_env["clients"]["res_pending"]
    revoked_client = test_env["clients"]["res_revoked"]

    # 1. Authenticate successfully on /auth/me
    me_pending = await pending_client.get("/api/v1/auth/me")
    assert me_pending.status_code == 200
    assert me_pending.json()["access_status"] == "pending_request"

    me_revoked = await revoked_client.get("/api/v1/auth/me")
    assert me_revoked.status_code == 200
    assert me_revoked.json()["access_status"] == "revoked"

    # 2. Blocked from research endpoints with explicit machine-readable code
    pending_docs = await pending_client.get("/api/v1/documents")
    assert pending_docs.status_code == 403
    assert pending_docs.json()["error"] == "access_pending"

    pending_sessions = await pending_client.get("/api/v1/research/sessions")
    assert pending_sessions.status_code == 403
    assert pending_sessions.json()["error"] == "access_pending"

    revoked_docs = await revoked_client.get("/api/v1/documents")
    assert revoked_docs.status_code == 403
    assert revoked_docs.json()["error"] == "access_revoked"


@pytest.mark.asyncio
async def test_access_request_and_invitation_lifecycle(test_env):
    """End-to-end flow: request access -> admin approves & issues token -> redeem -> active workspace."""
    pending_client = test_env["clients"]["res_pending"]
    admin_client = test_env["clients"]["admin"]
    anon_client = test_env["clients"]["anonymous"]

    # 1. Pending researcher submits access request
    req_payload = {
        "institution": "Institute for Environmental Research",
        "research_purpose": "Investigating global Extended Producer Responsibility policy frameworks and recycling targets.",
        "intended_data_types": "academic_papers",
    }
    submit_resp = await pending_client.post("/api/v1/auth/access-request", json=req_payload)
    assert submit_resp.status_code == 201, f"Failed to submit access request: {submit_resp.text}"
    req_data = submit_resp.json()
    req_id = req_data["id"]
    assert req_data["status"] == "pending"

    # Verify user access_status transitioned to request_submitted
    me_resp = await pending_client.get("/api/v1/auth/me")
    assert me_resp.json()["access_status"] == "request_submitted"

    # 2. Admin views access requests and approves
    admin_reqs = await admin_client.get("/api/v1/admin/access-requests?status=pending")
    assert admin_reqs.status_code == 200
    assert any(r["id"] == req_id for r in admin_reqs.json())

    approve_resp = await admin_client.post(
        f"/api/v1/admin/access-requests/{req_id}/approve",
        json={"expires_in_days": 7},
    )
    assert approve_resp.status_code == 200, f"Admin approval failed: {approve_resp.text}"
    inv_data = approve_resp.json()
    raw_token = inv_data["invitation_token"]
    assert raw_token is not None and len(raw_token) > 20

    # User access_status transitioned to approved_invitation_pending
    me_after_approve = await pending_client.get("/api/v1/auth/me")
    assert me_after_approve.json()["access_status"] == "approved_invitation_pending"

    # Still restricted until token redemption
    docs_before_redeem = await pending_client.get("/api/v1/documents")
    assert docs_before_redeem.status_code == 403
    assert docs_before_redeem.json()["error"] == "invitation_pending"

    # 3. Redeem cryptographic invitation token
    redeem_resp = await anon_client.post(
        "/api/v1/auth/invitations/redeem",
        json={"invitation_token": raw_token},
    )
    assert redeem_resp.status_code == 200, f"Token redemption failed: {redeem_resp.text}"

    # 4. User access_status is now active and research access is granted
    me_active = await pending_client.get("/api/v1/auth/me")
    assert me_active.json()["access_status"] == "active"

    docs_active = await pending_client.get("/api/v1/documents")
    assert docs_active.status_code == 200


@pytest.mark.asyncio
async def test_admin_anti_lockout_safeguards(test_env):
    """Admin cannot self-revoke or self-demote."""
    admin_client = test_env["clients"]["admin"]
    admin_id = test_env["users"]["admin"]

    # 1. Self-revocation attempt
    revoke_resp = await admin_client.post(
        f"/api/v1/admin/users/{admin_id}/revoke",
        json={"reason": "Self-inflicted lock"},
    )
    assert revoke_resp.status_code in (400, 403)
    assert "anti-lockout" in revoke_resp.text.lower() or "cannot" in revoke_resp.text.lower()

    # 2. Self-demotion attempt
    demote_resp = await admin_client.post(
        f"/api/v1/admin/users/{admin_id}/role",
        json={"role": "researcher"},
    )
    assert demote_resp.status_code in (400, 403)
    assert "anti-lockout" in demote_resp.text.lower() or "cannot" in demote_resp.text.lower()


@pytest.mark.asyncio
async def test_background_worker_enforces_revocation(test_env):
    """Ingestion worker aborts job and marks failed if document owner has revoked access."""
    session_maker = test_env["session_maker"]
    revoked_user_id = test_env["users"]["res_revoked"]

    # Enqueue a document for the revoked user
    async with session_maker() as session:
        doc = Document(
            id="doc_revoked_owner_01",
            owner_id=revoked_user_id,
            filename="orphan_study.pdf",
            storage_key="docs/orphan_study.pdf",
            content_hash="hash_orphan_01",
            file_size=2048,
            page_count=3,
            status="queued",
        )
        session.add(doc)
        await session.commit()

    # Instantiate worker and run recovery / process job
    worker = DurableIngestionWorker()

    # Patch AsyncSessionLocal for worker to use test DB session
    from app.services.ingestion import worker as worker_mod
    original_session_local = worker_mod.AsyncSessionLocal
    worker_mod.AsyncSessionLocal = session_maker

    try:
        did_process = await worker.process_next_job()
        assert did_process is True

        # Verify document status was marked failed and not processed
        async with session_maker() as session:
            updated_doc = (await session.execute(select(Document).where(Document.id == "doc_revoked_owner_01"))).scalar_one()
            assert updated_doc.status == "failed"
            assert "restricted" in updated_doc.processing_error.lower() or "revoked" in updated_doc.processing_error.lower()
    finally:
        worker_mod.AsyncSessionLocal = original_session_local

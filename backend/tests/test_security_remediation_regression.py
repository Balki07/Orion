"""Targeted Security Remediation Regression Test Suite.

Verifies:
1. SEC-05: Unauthenticated access to /api/v1/settings and /api/v1/settings/system is rejected (HTTP 401).
2. SEC-05: Pending and revoked researchers cannot access system diagnostics (HTTP 403).
3. SEC-05: Active researchers can access legitimate researcher settings (/api/v1/settings) but are forbidden from system diagnostics (/api/v1/settings/system) (HTTP 403).
4. SEC-05: Administrators have full access to both /api/v1/settings and /api/v1/settings/system.
5. SEC-04: Concurrent invitation redemption is atomic; exactly one request succeeds under concurrency.
6. SEC-04: Invitation token replay is rejected (HTTP 400).
7. SEC-04: Expired invitation tokens are rejected (HTTP 400).
"""

import asyncio
from datetime import UTC, datetime, timedelta
import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base, generate_uuid
from app.main import app
from app.models.access_control import Invitation
from app.models.user import User, UserSession
from app.security.service import auth_rate_limiter, create_session_jwt, hash_token


@pytest.fixture
async def remediation_db(tmp_path):
    """Isolated test database fixture with full schema and DEV_AUTH_BYPASS disabled."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    auth_rate_limiter.clear()

    test_db_url = f"sqlite+aiosqlite:///{tmp_path}/remediation_test.db"
    test_engine = create_async_engine(test_db_url, connect_args={"check_same_thread": False})
    SessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield SessionLocal

    app.dependency_overrides.clear()
    auth_rate_limiter.clear()
    settings.DEV_AUTH_BYPASS = orig_bypass
    await test_engine.dispose()


async def create_user_with_session(
    session_factory,
    email: str,
    role: str = "researcher",
    access_status: str = "active",
) -> tuple[User, str]:
    """Helper to provision a user and an active session token."""
    raw_session_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_session_token)

    async with session_factory() as db:
        user = User(
            id=generate_uuid("usr_"),
            email=email.strip().lower(),
            hashed_password="mock_argon2id_hash_value_123456",
            display_name="Test User",
            status="active",
            is_active=True,
            role=role,
            access_status=access_status,
        )
        db.add(user)
        await db.flush()

        sess = UserSession(
            id=generate_uuid("sess_"),
            user_id=user.id,
            session_token_hash=token_h,
            ip_address="127.0.0.1",
            user_agent="pytest-client",
            is_revoked=False,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(sess)
        await db.commit()

        jwt_token = create_session_jwt(user.id, user.email, sess.id)
        return user, jwt_token


# ==============================================================================
# SEC-05: Route Authorization on /settings and /settings/system
# ==============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_settings_access_rejected(remediation_db):
    """Verify that unauthenticated requests to settings endpoints return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Researcher settings without auth
        res1 = await client.get("/api/v1/settings")
        assert res1.status_code == 401
        assert res1.json()["error"] == "UNAUTHENTICATED"

        # 2. System diagnostics without auth
        res2 = await client.get("/api/v1/settings/system")
        assert res2.status_code == 401
        assert res2.json()["error"] == "UNAUTHENTICATED"

        # 3. System settings alias without auth
        res3 = await client.get("/api/v1/system/settings")
        assert res3.status_code == 401
        assert res3.json()["error"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_pending_researcher_settings_access_restricted(remediation_db):
    """Verify that pending researchers cannot access system diagnostics or active researcher settings."""
    _, jwt_token = await create_user_with_session(
        remediation_db,
        email="pending_researcher@test.orion.ai",
        role="researcher",
        access_status="pending_request",
    )
    headers = {"Authorization": f"Bearer {jwt_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # System diagnostics requires admin -> 403
        sys_res = await client.get("/api/v1/settings/system", headers=headers)
        assert sys_res.status_code == 403
        assert sys_res.json()["error"] == "FORBIDDEN_ACCESS"

        # Researcher settings requires active researcher -> 403 access_pending
        res_settings = await client.get("/api/v1/settings", headers=headers)
        assert res_settings.status_code == 403
        assert res_settings.json()["error"] == "access_pending"


@pytest.mark.asyncio
async def test_active_researcher_settings_access_allowed(remediation_db):
    """Verify that active researchers can retrieve researcher settings, but are forbidden from system diagnostics."""
    _, jwt_token = await create_user_with_session(
        remediation_db,
        email="active_researcher@test.orion.ai",
        role="researcher",
        access_status="active",
    )
    headers = {"Authorization": f"Bearer {jwt_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Researcher settings -> 200 OK
        res = await client.get("/api/v1/settings", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "app_name" in data
        assert "active_gemini_model" in data
        assert "max_upload_size_mb" in data

        # 2. System diagnostics -> 403 Forbidden (Admin only)
        sys_res = await client.get("/api/v1/settings/system", headers=headers)
        assert sys_res.status_code == 403
        assert sys_res.json()["error"] == "FORBIDDEN_ACCESS"

        # 3. System settings alias -> 403 Forbidden
        alias_res = await client.get("/api/v1/system/settings", headers=headers)
        assert alias_res.status_code == 403
        assert alias_res.json()["error"] == "FORBIDDEN_ACCESS"


@pytest.mark.asyncio
async def test_admin_system_diagnostics_access_allowed(remediation_db):
    """Verify that administrators can access both /settings and /settings/system."""
    _, jwt_token = await create_user_with_session(
        remediation_db,
        email="orionadmin@gmail.com",
        role="admin",
        access_status="active",
    )
    headers = {"Authorization": f"Bearer {jwt_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Researcher settings -> 200 OK
        res1 = await client.get("/api/v1/settings", headers=headers)
        assert res1.status_code == 200

        # 2. System diagnostics -> 200 OK
        res2 = await client.get("/api/v1/settings/system", headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert "active_embedding_model" in data2
        assert "chunk_size" in data2
        assert "hybrid_fusion_alpha" in data2

        # 3. System settings alias -> 200 OK
        res3 = await client.get("/api/v1/system/settings", headers=headers)
        assert res3.status_code == 200


# ==============================================================================
# SEC-04: Atomic Invitation Redemption & Concurrency Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_invitation_redemption_atomic(remediation_db):
    """Verify that concurrent requests attempting to redeem the same token execute atomically."""
    # 1. Create target user in approved_invitation_pending status
    user, _ = await create_user_with_session(
        remediation_db,
        email="concurrent_invitee@test.orion.ai",
        role="researcher",
        access_status="approved_invitation_pending",
    )

    # 2. Issue raw invitation token and store hash
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)

    async with remediation_db() as db:
        invitation = Invitation(
            id=generate_uuid("inv_"),
            user_id=user.id,
            token_hash=token_h,
            created_by=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            is_redeemed=False,
        )
        db.add(invitation)
        await db.commit()

    # 3. Fire 5 concurrent redemption requests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def attempt_redemption():
            return await client.post(
                "/api/v1/auth/invitations/redeem",
                json={"invitation_token": raw_token},
            )

        responses = await asyncio.gather(*[attempt_redemption() for _ in range(5)])

    # 4. Assert exactly ONE request succeeded (HTTP 200) and four were rejected (HTTP 400)
    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 1, f"Expected exactly 1 success, got: {status_codes}"
    assert status_codes.count(400) == 4, f"Expected 4 rejections, got: {status_codes}"

    # 5. Verify database state
    async with remediation_db() as db:
        u_res = await db.execute(select(User).where(User.id == user.id))
        updated_user = u_res.scalar_one()
        assert updated_user.access_status == "active"

        inv_res = await db.execute(select(Invitation).where(Invitation.token_hash == token_h))
        updated_inv = inv_res.scalar_one()
        assert updated_inv.is_redeemed is True
        assert updated_inv.redeemed_at is not None


@pytest.mark.asyncio
async def test_token_replay_rejected(remediation_db):
    """Verify that a redeemed token cannot be reused in subsequent requests."""
    user, _ = await create_user_with_session(
        remediation_db,
        email="replay_test_user@test.orion.ai",
        role="researcher",
        access_status="approved_invitation_pending",
    )
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)

    async with remediation_db() as db:
        invitation = Invitation(
            id=generate_uuid("inv_"),
            user_id=user.id,
            token_hash=token_h,
            created_by=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            is_redeemed=False,
        )
        db.add(invitation)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First redemption -> 200 OK
        r1 = await client.post("/api/v1/auth/invitations/redeem", json={"invitation_token": raw_token})
        assert r1.status_code == 200

        # Second redemption attempt -> 400 Bad Request
        r2 = await client.post("/api/v1/auth/invitations/redeem", json={"invitation_token": raw_token})
        assert r2.status_code == 400
        assert r2.json()["detail"] == "This invitation token has already been redeemed."


@pytest.mark.asyncio
async def test_expired_invitation_rejected(remediation_db):
    """Verify that an expired invitation token cannot be redeemed."""
    user, _ = await create_user_with_session(
        remediation_db,
        email="expired_invitee@test.orion.ai",
        role="researcher",
        access_status="approved_invitation_pending",
    )
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)

    async with remediation_db() as db:
        invitation = Invitation(
            id=generate_uuid("inv_"),
            user_id=user.id,
            token_hash=token_h,
            created_by=user.id,
            expires_at=datetime.now(UTC) - timedelta(hours=2),  # Already expired
            is_redeemed=False,
        )
        db.add(invitation)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/invitations/redeem", json={"invitation_token": raw_token})
        assert r.status_code == 400
        assert r.json()["detail"] == "This invitation token has expired."

"""Verification of Primary Administrator (orionadmin@gmail.com) Configuration & Security."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.security.service import auth_rate_limiter, hash_password


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter before each test."""
    auth_rate_limiter.clear()
    yield
    auth_rate_limiter.clear()


@pytest.mark.asyncio
async def test_admin_emails_configuration_and_case_insensitivity():
    """Verify orionadmin@gmail.com is configured and role resolution is case/whitespace-safe."""
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    assert "orionadmin@gmail.com" in admin_emails

    # Test case variations and whitespace
    variations = [
        "orionadmin@gmail.com",
        "ORIONADMIN@GMAIL.COM",
        "  orionadmin@gmail.com  ",
        "OrionAdmin@Gmail.com",
    ]
    for variant in variations:
        cleaned = variant.strip().lower()
        assert cleaned in admin_emails


@pytest.mark.asyncio
async def test_primary_admin_login_me_and_admin_api_access():
    """Verify orionadmin@gmail.com can log in, receive role: admin, and access all admin APIs."""
    primary_email = "orionadmin@gmail.com"
    test_password = "PrimaryAdminPassword!2026"

    # Ensure user exists in database with Argon2id hash
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.email == primary_email)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                email=primary_email,
                hashed_password=hash_password(test_password),
                display_name="ORION Administrator",
                institution="ORION System Administration",
                status="active",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            user.hashed_password = hash_password(test_password)
            user.status = "active"
            user.is_active = True
            await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with uppercase email variant to test whitespace and case-safety
        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "  OrionAdmin@Gmail.com  ",
                "password": test_password,
            },
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        data = login_res.json()
        assert data["user"]["email"] == primary_email
        assert data["user"]["role"] == "admin"
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Verify /api/v1/auth/me returns role: admin
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == primary_email
        assert me_data["role"] == "admin"
        assert "hashed_password" not in me_data

        # 3. Verify Admin APIs return HTTP 200 for orionadmin@gmail.com
        admin_endpoints = [
            "/api/v1/admin/overview",
            "/api/v1/admin/users",
            "/api/v1/admin/system-health",
            "/api/v1/admin/analytics/registrations",
            "/api/v1/admin/analytics/logins",
            "/api/v1/admin/analytics/documents",
            "/api/v1/admin/analytics/ai-usage",
        ]
        for ep in admin_endpoints:
            res = await client.get(ep, headers=headers)
            assert res.status_code == 200, f"Expected 200 for {ep}, got {res.status_code}"


@pytest.mark.asyncio
async def test_normal_researcher_receives_http_403():
    """Verify non-admin researcher receives HTTP 403 on all admin endpoints."""
    reg_email = "nonadmin.researcher@orion.ai"
    reg_pass = "ResearcherPassword!2026"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": reg_email,
                "password": reg_pass,
                "display_name": "Standard Researcher",
            },
        )
        assert reg_res.status_code in (201, 409)

        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": reg_email,
                "password": reg_pass,
            },
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        assert login_res.json()["user"]["role"] in ("researcher", "authenticated")

        # Verify /auth/me returns researcher/authenticated (not admin)
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["role"] in ("researcher", "authenticated")

        # Attempt to access admin endpoints
        for ep in ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/system-health"]:
            res = await client.get(ep, headers=headers)
            assert res.status_code == 403, f"Expected 403 for {ep}, got {res.status_code}"


@pytest.mark.asyncio
async def test_unauthenticated_request_receives_http_401():
    """Verify unauthenticated caller receives HTTP 401 Unauthorized."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for ep in ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/system-health"]:
                res = await client.get(ep)
                assert res.status_code == 401, f"Expected 401 for {ep}, got {res.status_code}"
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_admin_user_ids_preserved():
    """Verify ADMIN_USER_IDS functionality is preserved."""
    admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
    assert "user_admin_001" in admin_ids


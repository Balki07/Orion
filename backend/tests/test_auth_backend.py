"""Unit and Integration Tests for Real Backend Authentication Foundation."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.config import settings
from app.core.errors import DuplicateEmailError, InvalidCredentialsError
from app.db.base import generate_uuid
from app.main import app
from app.models.user import User, UserSession
from app.security.service import (
    auth_rate_limiter,
    create_session_jwt,
    hash_password,
    hash_token,
    normalize_email,
    validate_password_strength,
    verify_password,
)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter state before each test."""
    auth_rate_limiter.clear()
    yield
    auth_rate_limiter.clear()


@pytest.mark.asyncio
async def test_argon2id_hashing_and_verification():
    """Verify Argon2id password hashing parameters and verification behavior."""
    raw_password = "SecureResearchPass!2026"
    hashed = hash_password(raw_password)

    # Must be valid Argon2id hash with OWASP memory and time parameters
    assert hashed.startswith("$argon2id$v=19$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!2026", hashed) is False
    assert verify_password("", hashed) is False


def test_password_strength_validation():
    """Verify password strength validation rules."""
    # Valid
    validate_password_strength("ValidPassw0rd!")

    # Too short
    with pytest.raises(ValueError, match="at least 8 characters"):
        validate_password_strength("Short1!")

    # Missing uppercase
    with pytest.raises(ValueError, match="uppercase letter"):
        validate_password_strength("alllowercase1!")

    # Missing lowercase
    with pytest.raises(ValueError, match="lowercase letter"):
        validate_password_strength("ALLLOWERCASE1!")

    # Missing digit
    with pytest.raises(ValueError, match="digit"):
        validate_password_strength("NoDigitsHere!")

    # Missing special character
    with pytest.raises(ValueError, match="special character"):
        validate_password_strength("NoSpecialChar123")


def test_email_normalization():
    """Verify email normalization and invalid email rejection."""
    assert normalize_email("  Researcher.One@Example.COM  ") == "researcher.one@example.com"
    assert normalize_email("user+test@domain.co.uk") == "user+test@domain.co.uk"

    with pytest.raises(ValueError, match="format"):
        normalize_email("not-an-email")

    with pytest.raises(ValueError, match="empty"):
        normalize_email("")


@pytest.mark.asyncio
async def test_successful_user_registration():
    """Test POST /api/v1/auth/register creates user, session, and cookies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "dr.doe@oxford.ac.uk",
            "password": "StrongPassword!2026",
            "display_name": "Dr. Jane Doe",
            "institution": "University of Oxford",
        }
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()

        # Check response structure
        assert "user" in data
        assert data["user"]["email"] == "dr.doe@oxford.ac.uk"
        assert data["user"]["display_name"] == "Dr. Jane Doe"
        assert data["user"]["institution"] == "University of Oxford"
        assert data["user"]["status"] == "active"
        assert "hashed_password" not in data["user"]
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "csrf_token" in data

        # Check cookies set
        cookies = res.cookies
        assert settings.SESSION_COOKIE_NAME in cookies
        assert settings.CSRF_COOKIE_NAME in cookies


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected():
    """Test POST /api/v1/auth/register rejects duplicate email with 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": "duplicate.test@orion.ai",
            "password": "StrongPassword!2026",
            "display_name": "First User",
        }
        res1 = await client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        # Second registration with same email (even with different case and whitespace)
        duplicate_payload = {
            "email": "  DUPLICATE.TEST@ORION.AI  ",
            "password": "AnotherPassword!2026",
            "display_name": "Second User",
        }
        res2 = await client.post("/api/v1/auth/register", json=duplicate_payload)
        assert res2.status_code == 409
        err = res2.json()
        assert err["error"] == "DUPLICATE_EMAIL"


@pytest.mark.asyncio
async def test_successful_user_login():
    """Test POST /api/v1/auth/login authenticates valid credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user first
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login.user@orion.ai",
                "password": "CorrectPassword!2026",
                "display_name": "Login Tester",
            },
        )

        # Login with correct credentials
        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login.user@orion.ai",
                "password": "CorrectPassword!2026",
            },
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert data["user"]["email"] == "login.user@orion.ai"
        assert "access_token" in data
        assert settings.SESSION_COOKIE_NAME in login_res.cookies


@pytest.mark.asyncio
async def test_login_incorrect_password_rejected():
    """Test POST /api/v1/auth/login rejects incorrect password with generic error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "security.audit@orion.ai",
                "password": "RealPassword!2026",
                "display_name": "Audit User",
            },
        )

        bad_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "security.audit@orion.ai",
                "password": "WrongPassword!2026",
            },
        )
        assert bad_res.status_code == 401
        err = bad_res.json()
        assert err["error"] == "INVALID_CREDENTIALS"
        assert "Invalid email or password" in err["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email_rejected():
    """Test POST /api/v1/auth/login rejects unknown email safely."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@orion.ai",
                "password": "SomePassword!2026",
            },
        )
        assert res.status_code == 401
        assert res.json()["error"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_get_me_authenticated_via_bearer():
    """Test GET /api/v1/auth/me using Authorization: Bearer <token>."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "bearer.auth@orion.ai",
                "password": "BearerPassword!2026",
                "display_name": "Bearer User",
            },
        )
        token = reg_res.json()["access_token"]

        # Call /me with Bearer token (clearing cookies to isolate Bearer header)
        client.cookies.clear()
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "bearer.auth@orion.ai"
        assert me_res.json()["display_name"] == "Bearer User"


@pytest.mark.asyncio
async def test_get_me_authenticated_via_cookie():
    """Test GET /api/v1/auth/me using HttpOnly session cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "cookie.auth@orion.ai",
                "password": "CookiePassword!2026",
                "display_name": "Cookie User",
            },
        )
        # Client automatically retains cookies from register response
        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "cookie.auth@orion.ai"


@pytest.mark.asyncio
async def test_csrf_protection_on_cookie_mutation():
    """Test that cookie-authenticated mutation endpoints reject missing/invalid CSRF token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf.tester@orion.ai",
                "password": "CsrfPassword!2026",
                "display_name": "CSRF Tester",
            },
        )
        token = reg_res.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf = reg_res.cookies.get(settings.CSRF_COOKIE_NAME)

        # 1. State-changing request with cookie but without X-CSRF-Token header -> must be rejected
        client.cookies.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, token)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf)

        # Perform a state-changing POST (e.g. /logout) without X-CSRF-Token header
        bad_csrf = await client.post("/api/v1/auth/logout")
        assert bad_csrf.status_code == 403
        assert bad_csrf.json()["error"] == "CSRF_VALIDATION_FAILED"

        # 2. State-changing request with valid X-CSRF-Token header -> succeeds
        good_csrf = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert good_csrf.status_code == 200


@pytest.mark.asyncio
async def test_get_me_unauthenticated_without_bypass():
    """Test GET /api/v1/auth/me returns 401 when unauthenticated and DEV_AUTH_BYPASS is disabled."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.clear()
            me_res = await client.get("/api/v1/auth/me")
            assert me_res.status_code == 401
            assert me_res.json()["error"] == "UNAUTHENTICATED"
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_logout_and_session_invalidation():
    """Test POST /api/v1/auth/logout invalidates session and prevents further access."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reg_res = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "logout.test@orion.ai",
                    "password": "LogoutPass!2026",
                    "display_name": "Logout Tester",
                },
            )
            token = reg_res.json()["access_token"]

            # Verify /me succeeds before logout
            me_before = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_before.status_code == 200

            # Logout
            logout_res = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert logout_res.status_code == 200
            assert "Logged out" in logout_res.json()["message"]

            # Attempt /me again with the same token -> must be rejected
            me_after = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_after.status_code == 401
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_expired_session_rejected():
    """Test that expired session tokens are rejected."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        # Create token that expired 10 minutes ago
        past_delta = timedelta(minutes=-10)
        expired_token = create_session_jwt(
            user_id="usr_expired_test",
            email="expired@orion.ai",
            session_id="sess_expired_test",
            expires_delta=past_delta,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
            assert res.status_code == 401
            assert "expired" in res.json()["detail"].lower()
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_login_rate_limiting():
    """Test that repeated login attempts trigger rate limiting (HTTP 429)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt login 6 times (limit is 5)
        for i in range(settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS):
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "ratelimit@orion.ai", "password": "WrongPassword!2026"},
            )
            assert res.status_code == 401

        # 6th attempt should be rate limited
        blocked_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@orion.ai", "password": "WrongPassword!2026"},
        )
        assert blocked_res.status_code == 429
        assert blocked_res.json()["error"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_registration_rate_limiting():
    """Test that repeated registration attempts from same IP trigger rate limiting (HTTP 429)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Limit is 3 registration attempts per window
        for i in range(settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS):
            res = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"ratelimit.reg{i}@orion.ai",
                    "password": "StrongPassword!2026",
                    "display_name": f"User {i}",
                },
            )
            assert res.status_code == 201

        # 4th attempt should be blocked
        blocked_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "ratelimit.reg_blocked@orion.ai",
                "password": "StrongPassword!2026",
                "display_name": "Blocked User",
            },
        )
        assert blocked_res.status_code == 429
        assert blocked_res.json()["error"] == "RATE_LIMIT_EXCEEDED"


def test_postgresql_ddl_compilation():
    """Verify that User and UserSession models compile cleanly for PostgreSQL dialect."""
    pg_dialect = postgresql.dialect()

    user_ddl = str(CreateTable(User.__table__).compile(dialect=pg_dialect))
    session_ddl = str(CreateTable(UserSession.__table__).compile(dialect=pg_dialect))

    # Check key PostgreSQL types and constraints
    assert "VARCHAR(255)" in user_ddl
    assert "BOOLEAN" in user_ddl
    assert "TIMESTAMP WITH TIME ZONE" in user_ddl
    assert "VARCHAR(64)" in session_ddl
    assert "FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE" in session_ddl

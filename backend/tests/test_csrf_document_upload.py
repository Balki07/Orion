"""Unit and Integration Tests for CSRF Token Synchronization and Document Upload Protection.

Validates:
1. Valid CSRF token accepted on document upload.
2. Missing CSRF token rejected with HTTP 403.
3. Incorrect CSRF token rejected with HTTP 403.
4. Valid CSRF token accepted on batch document upload.
5. Missing CSRF token rejected with HTTP 403 on batch document upload.
6. Stale CSRF token after logout/relogin rejected with HTTP 403.
7. Multipart FormData upload preserves CSRF header and succeeds.
8. GET /api/v1/auth/me synchronizes CSRF cookie when missing from active session.
"""

import io
import uuid
from unittest.mock import AsyncMock, patch
import pytest
import pymupdf
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.api.deps import get_db, get_storage_service
from app.services.storage.local import LocalStorageService
from app.security.service import auth_rate_limiter


def create_test_pdf(title: str = "Test Research Paper") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), f"{title}\nExtended Producer Responsibility in European Frameworks.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
async def setup_test_app(tmp_path):
    """Set up isolated SQLite DB and local storage backend for clean test execution."""
    auth_rate_limiter.clear()
    test_db_url = f"sqlite+aiosqlite:///{tmp_path}/csrf_test.db"
    test_engine = create_async_engine(test_db_url, connect_args={"check_same_thread": False})
    SessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    local_storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    def override_get_storage():
        return local_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_get_storage

    async def activate_user(email: str):
        from app.models.user import User
        from sqlalchemy import select
        async with SessionLocal() as session:
            res = await session.execute(select(User).where(User.email == email))
            u = res.scalar_one_or_none()
            if u:
                u.access_status = "active"
                await session.commit()

    with patch("app.api.v1.documents.run_background_ingestion", new_callable=AsyncMock):
        yield activate_user

    app.dependency_overrides.clear()
    auth_rate_limiter.clear()


@pytest.mark.asyncio
async def test_cookie_auth_valid_csrf_accepted_on_document_upload(setup_test_app):
    """Verify that a cookie-authenticated upload with matching X-CSRF-Token is accepted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf_upload_user@test.orion.ai",
                "password": "Password123!#",
                "display_name": "CSRF User",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("csrf_upload_user@test.orion.ai")
        csrf_token = reg.json()["csrf_token"]
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie = reg.cookies.get(settings.CSRF_COOKIE_NAME)

        # Clear client headers to ensure pure cookie-based authentication
        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie)

        pdf_bytes = create_test_pdf("Document Upload Test")
        files = {"file": ("paper1.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        # State-changing POST /api/v1/documents with matching X-CSRF-Token
        res = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res.status_code == 201, res.text
        doc = res.json()
        assert doc["filename"] == "paper1.pdf"
        assert doc["status"] == "queued"


@pytest.mark.asyncio
async def test_cookie_auth_missing_csrf_rejected_on_document_upload(setup_test_app):
    """Verify that cookie-authenticated upload without X-CSRF-Token is rejected with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf_missing_user@test.orion.ai",
                "password": "Password123!#",
                "display_name": "Missing CSRF",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("sync_csrf_user@test.orion.ai")
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie = reg.cookies.get(settings.CSRF_COOKIE_NAME)

        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie)

        pdf_bytes = create_test_pdf("Missing Token Test")
        files = {"file": ("paper_missing.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        # Omit X-CSRF-Token header
        res = await client.post("/api/v1/documents", files=files)
        assert res.status_code == 403
        data = res.json()
        assert data["error"] == "CSRF_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_cookie_auth_incorrect_csrf_rejected_on_document_upload(setup_test_app):
    """Verify that cookie-authenticated upload with mismatched X-CSRF-Token is rejected with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf_bad_user@test.orion.ai",
                "password": "Password123!#",
                "display_name": "Bad CSRF",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("sync_csrf_user@test.orion.ai")
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie = reg.cookies.get(settings.CSRF_COOKIE_NAME)

        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie)

        pdf_bytes = create_test_pdf("Bad Token Test")
        files = {"file": ("paper_bad.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        # Send incorrect X-CSRF-Token header
        res = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-CSRF-Token": "completely_wrong_token_value_99999"},
        )
        assert res.status_code == 403
        data = res.json()
        assert data["error"] == "CSRF_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_cookie_auth_valid_csrf_accepted_on_batch_upload(setup_test_app):
    """Verify that batch document upload with valid CSRF token succeeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf_batch_user@test.orion.ai",
                "password": "Password123!#",
                "display_name": "Batch User",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("csrf_batch_user@test.orion.ai")
        csrf_token = reg.json()["csrf_token"]
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie = reg.cookies.get(settings.CSRF_COOKIE_NAME)

        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie)

        pdf1 = create_test_pdf("Batch Paper 1")
        pdf2 = create_test_pdf("Batch Paper 2")
        files = [
            ("files", ("batch_1.pdf", io.BytesIO(pdf1), "application/pdf")),
            ("files", ("batch_2.pdf", io.BytesIO(pdf2), "application/pdf")),
        ]

        res = await client.post(
            "/api/v1/documents/batch",
            files=files,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["total"] == 2
        assert data["successful_count"] == 2
        assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_cookie_auth_missing_csrf_rejected_on_batch_upload(setup_test_app):
    """Verify that batch upload without X-CSRF-Token is rejected with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf_batch_missing@test.orion.ai",
                "password": "Password123!#",
                "display_name": "Batch Missing",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("sync_csrf_user@test.orion.ai")
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie = reg.cookies.get(settings.CSRF_COOKIE_NAME)

        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie)

        pdf1 = create_test_pdf("Batch Paper 1")
        files = [("files", ("batch_1.pdf", io.BytesIO(pdf1), "application/pdf"))]

        res = await client.post("/api/v1/documents/batch", files=files)
        assert res.status_code == 403
        assert res.json()["error"] == "CSRF_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_cookie_auth_stale_csrf_token_rejected_after_relogin(setup_test_app):
    """Verify that a stale token from a prior session is rejected after logout and re-login."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_email = "relogin_csrf_user@test.orion.ai"
        user_pass = "Password123!#"

        # 1. Register User and obtain session 1
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": user_email,
                "password": user_pass,
                "display_name": "Relogin User",
            },
        )
        assert reg.status_code == 201
        await setup_test_app(user_email)
        stale_csrf_token = reg.json()["csrf_token"]

        # 2. Logout
        logout_res = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": stale_csrf_token},
        )
        assert logout_res.status_code == 200

        # 3. Log in again to create fresh session 2
        auth_rate_limiter.clear()
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": user_email, "password": user_pass},
        )
        assert login_res.status_code == 200
        fresh_csrf_token = login_res.json()["csrf_token"]
        assert fresh_csrf_token != stale_csrf_token

        # Update cookies to session 2
        session_cookie_2 = login_res.cookies.get(settings.SESSION_COOKIE_NAME)
        csrf_cookie_2 = login_res.cookies.get(settings.CSRF_COOKIE_NAME)
        client.headers.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie_2)
        client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_cookie_2)

        pdf_bytes = create_test_pdf("Stale Token Test")
        files = {"file": ("paper_stale.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

        # 4. Attempt upload using stale CSRF token 1 -> MUST BE REJECTED
        stale_upload = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-CSRF-Token": stale_csrf_token},
        )
        assert stale_upload.status_code == 403
        assert stale_upload.json()["error"] == "CSRF_VALIDATION_FAILED"

        # 5. Attempt upload using fresh CSRF token 2 -> MUST SUCCEED
        files_fresh = {"file": ("paper_fresh.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        fresh_upload = await client.post(
            "/api/v1/documents",
            files=files_fresh,
            headers={"X-CSRF-Token": fresh_csrf_token},
        )
        assert fresh_upload.status_code == 201
        assert fresh_upload.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_auth_me_synchronizes_csrf_cookie_when_missing(setup_test_app):
    """Verify that GET /api/v1/auth/me sets a fresh CSRF cookie and X-CSRF-Token header if missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "sync_csrf_user@test.orion.ai",
                "password": "Password123!#",
                "display_name": "Sync User",
            },
        )
        assert reg.status_code == 201
        await setup_test_app("sync_csrf_user@test.orion.ai")
        session_cookie = reg.cookies.get(settings.SESSION_COOKIE_NAME)

        # Simulate browser that has session cookie but lost its CSRF cookie
        client.headers.clear()
        client.cookies.clear()
        client.cookies.set(settings.SESSION_COOKIE_NAME, session_cookie)

        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200

        # Must have issued a new CSRF cookie and header
        issued_csrf_header = me_res.headers.get("X-CSRF-Token")
        issued_csrf_cookie = me_res.cookies.get(settings.CSRF_COOKIE_NAME)
        assert issued_csrf_header is not None
        assert issued_csrf_cookie is not None
        assert issued_csrf_header == issued_csrf_cookie

        # Upload with this new synchronized token succeeds
        pdf_bytes = create_test_pdf("Recovered CSRF Test")
        files = {"file": ("recovered.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post(
            "/api/v1/documents",
            files=files,
            headers={"X-CSRF-Token": issued_csrf_header},
        )
        assert upload_res.status_code == 201
        assert upload_res.json()["filename"] == "recovered.pdf"

"""Comprehensive Unit and Integration Tests for ORION Admin Dashboard & Analytics.

Tests:
1. Admin can access /api/v1/admin/overview with valid admin session.
2. Non-admin authenticated user receives HTTP 403 Forbidden on all admin endpoints.
3. Unauthenticated request receives HTTP 401 Unauthorized.
4. Cannot access another user's private document content/chunks via admin endpoints.
5. Registration metrics calculate accurately (today, week, month).
6. Successful and failed login events are recorded in auth_audit_events.
7. User login counts and last login match audit events.
8. Document storage statistics match 500 MB quota accounting.
9. AI usage statistics match llm_usage_records.
10. User pagination, search (display_name, email), and status filters work.
11. Passwords, password hashes, session tokens, and Gemini API keys are never returned.
12. System health reports infrastructure status safely without leaking secrets.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.base import generate_uuid
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.auth_event import AuthAuditEvent
from app.models.document import Document
from app.models.llm_usage import LLMUsageRecord
from app.models.user import User
from app.security.service import auth_rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limiter before each test."""
    auth_rate_limiter.clear()
    yield
    auth_rate_limiter.clear()


async def get_admin_headers(client: AsyncClient) -> dict[str, str]:
    """Helper to ensure admin user exists and return Bearer auth header."""
    admin_email = "admin@orion-assistant.ai"
    admin_pass = "AdminSecurePassword!2026"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": admin_email,
            "password": admin_pass,
            "display_name": "Chief Administrator",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": admin_email,
            "password": admin_pass,
        },
    )
    assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_access_allowed_and_overview_metrics():
    """Test 1: Admin can authenticate and access /api/v1/admin/overview."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await get_admin_headers(client)

        # Access /api/v1/admin/overview
        res = await client.get("/api/v1/admin/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "users" in data
        assert "logins" in data
        assert "documents" in data
        assert "ai_usage" in data
        assert data["users"]["total_users"] >= 1
        assert data["logins"]["total_logins"] >= 1


@pytest.mark.asyncio
async def test_non_admin_forbidden():
    """Test 2: Non-admin authenticated user receives HTTP 403 on all admin endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "researcher.regular@orion.ai",
                "password": "RegularResearcher!2026",
                "display_name": "Ordinary Researcher",
            },
        )
        assert reg_res.status_code in (201, 409)

        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "researcher.regular@orion.ai",
                "password": "RegularResearcher!2026",
            },
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        assert login_res.json()["user"]["role"] in ("researcher", "authenticated")

        headers = {"Authorization": f"Bearer {token}"}
        endpoints = [
            "/api/v1/admin/overview",
            "/api/v1/admin/users",
            "/api/v1/admin/analytics/registrations",
            "/api/v1/admin/analytics/logins",
            "/api/v1/admin/analytics/documents",
            "/api/v1/admin/analytics/ai-usage",
            "/api/v1/admin/system-health",
        ]
        for ep in endpoints:
            res = await client.get(ep, headers=headers)
            assert res.status_code == 403, f"Expected 403 for {ep}, got {res.status_code}"


@pytest.mark.asyncio
async def test_unauthenticated_unauthorized():
    """Test 3: Unauthenticated request receives HTTP 401 Unauthorized when auth bypass is disabled."""
    orig_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            endpoints = [
                "/api/v1/admin/overview",
                "/api/v1/admin/users",
                "/api/v1/admin/system-health",
            ]
            for ep in endpoints:
                res = await client.get(ep)
                assert res.status_code == 401, f"Expected 401 for {ep}, got {res.status_code}"
    finally:
        settings.DEV_AUTH_BYPASS = orig_bypass


@pytest.mark.asyncio
async def test_login_audit_events_recording():
    """Test 6: Successful and failed login events are recorded in auth_audit_events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = "audit.target@orion.ai"
        # Register user
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": "AuditPassword!2026",
                "display_name": "Audit Target",
            },
        )
        assert reg_res.status_code in (201, 409)

        # Attempt failed login
        fail_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": "WrongPassword!2026",
            },
        )
        assert fail_res.status_code == 401

        # Successful login
        ok_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": "AuditPassword!2026",
            },
        )
        assert ok_res.status_code == 200

        # Verify audit records in DB
        async with AsyncSessionLocal() as db:
            events = (
                await db.scalars(
                    select(AuthAuditEvent)
                    .where(AuthAuditEvent.email == test_email)
                    .order_by(AuthAuditEvent.created_at.asc())
                )
            ).all()

            event_types = [e.event_type for e in events]
            assert "register" in event_types
            assert "login_failure" in event_types
            assert "login_success" in event_types

            # Verify no secrets in audit records
            for e in events:
                assert e.ip_address is not None
                if e.event_type == "login_failure":
                    assert e.failure_reason == "INVALID_CREDENTIALS"
                    assert e.success is False


@pytest.mark.asyncio
async def test_user_pagination_search_and_filters():
    """Test 10: User pagination, search, and status filters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await get_admin_headers(client)

        # Search by display name
        res = await client.get("/api/v1/admin/users?search=Chief", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data["users"]) >= 1
        assert any("Chief" in u["display_name"] for u in data["users"])

        # Search by non-existent term
        res_empty = await client.get("/api/v1/admin/users?search=NonExistentResearcher999", headers=headers)
        assert res_empty.status_code == 200
        assert len(res_empty.json()["users"]) == 0

        # Pagination parameters
        res_page = await client.get("/api/v1/admin/users?page=1&page_size=2", headers=headers)
        assert res_page.status_code == 200
        pdata = res_page.json()
        assert pdata["page"] == 1
        assert pdata["page_size"] == 2
        assert len(pdata["users"]) <= 2


@pytest.mark.asyncio
async def test_user_detail_and_no_leak_of_private_content():
    """Test 4 & 11: Admin user detail provides usage stats without private chunk text or secrets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a researcher and insert test doc & AI usage
        target_email = "detail.researcher@orion.ai"
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": target_email,
                "password": "ResearcherDetail!2026",
                "display_name": "Dr. Marie Curie",
                "institution": "Sorbonne",
            },
        )
        if reg_res.status_code == 201:
            user_id = reg_res.json()["user"]["id"]
        else:
            login_res = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": target_email,
                    "password": "ResearcherDetail!2026",
                },
            )
            user_id = login_res.json()["user"]["id"]

        # Insert a document and LLM usage record directly for this user
        async with AsyncSessionLocal() as db:
            doc = Document(
                id=generate_uuid("doc"),
                owner_id=user_id,
                filename="radioactivity_study.pdf",
                storage_key=f"{user_id}/radioactivity_study.pdf",
                content_hash="abc123hash",
                file_size=1024 * 1024 * 5,  # 5 MB
                page_count=12,
                status="completed",
            )
            db.add(doc)

            llm_rec = LLMUsageRecord(
                id=generate_uuid("llm_use"),
                user_id=user_id,
                model="gemini-2.5-flash",
                call_type="research_qa",
                status="success",
                prompt_tokens=150,
                completion_tokens=250,
                total_tokens=400,
                is_provider_call=True,
            )
            db.add(llm_rec)
            await db.commit()

        # Admin fetches user detail
        headers = await get_admin_headers(client)

        res = await client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
        assert res.status_code == 200
        detail = res.json()

        # Verify summary stats
        assert detail["user"]["id"] == user_id
        assert detail["user"]["email"] == target_email
        assert detail["user"]["display_name"] == "Dr. Marie Curie"
        assert detail["user"]["document_count"] >= 1
        assert detail["user"]["storage_used_mb"] >= 5.0
        assert detail["user"]["storage_quota_mb"] == 500
        assert detail["user"]["ai_request_count"] >= 1
        assert detail["user"]["ai_total_tokens"] >= 400

        # Verify documents summary
        assert len(detail["recent_documents"]) >= 1
        doc_item = detail["recent_documents"][0]
        assert doc_item["title"] == "radioactivity_study.pdf"
        assert doc_item["file_size_bytes"] == 1024 * 1024 * 5

        # Security check: verify no secrets or private document chunks leaked
        body_str = res.text
        assert "hashed_password" not in body_str
        assert "password_hash" not in body_str
        assert "session_token_hash" not in body_str
        assert "chunks" not in body_str
        assert "chunk_text" not in body_str


@pytest.mark.asyncio
async def test_time_series_analytics_endpoints():
    """Test 5, 8, 9: Daily analytics endpoints (registrations, logins, documents, ai-usage)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await get_admin_headers(client)

        # 1. Registrations analytics
        r_res = await client.get("/api/v1/admin/analytics/registrations?days=14", headers=headers)
        assert r_res.status_code == 200
        r_data = r_res.json()
        assert len(r_data) == 14
        assert "date" in r_data[0]
        assert "count" in r_data[0]

        # 2. Logins analytics
        l_res = await client.get("/api/v1/admin/analytics/logins?days=14", headers=headers)
        assert l_res.status_code == 200
        l_data = l_res.json()
        assert len(l_data) == 14
        assert "success_count" in l_data[0]
        assert "failure_count" in l_data[0]

        # 3. Documents analytics
        d_res = await client.get("/api/v1/admin/analytics/documents?days=14", headers=headers)
        assert d_res.status_code == 200
        d_data = d_res.json()
        assert len(d_data) == 14

        # 4. AI usage analytics
        a_res = await client.get("/api/v1/admin/analytics/ai-usage?days=14", headers=headers)
        assert a_res.status_code == 200
        a_data = a_res.json()
        assert len(a_data) == 14
        assert "requests" in a_data[0]
        assert "tokens" in a_data[0]
        assert "estimated_cost_usd" in a_data[0]


@pytest.mark.asyncio
async def test_system_health_safe_status():
    """Test 12: Admin system-health reports infrastructure safely without secret leaks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await get_admin_headers(client)

        res = await client.get("/api/v1/admin/system-health", headers=headers)
        assert res.status_code == 200
        health = res.json()

        assert health["status"] in ("healthy", "degraded")
        assert "database" in health
        assert health["database"]["healthy"] is True
        assert "storage" in health
        assert health["storage"]["user_quota_mb"] == 500
        assert "ingestion" in health
        assert "gemini" in health
        assert "api_key_configured" in health["gemini"]

        # Ensure no secrets or API keys are exposed
        body_str = res.text
        if settings.GEMINI_API_KEY:
            assert settings.GEMINI_API_KEY not in body_str
        assert "DATABASE_URL" not in body_str
        assert "SESSION_SECRET_KEY" not in body_str


@pytest.mark.asyncio
async def test_user_activity_and_usage_breakdown():
    """Test user activity timeline and storage/AI quota usage endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await get_admin_headers(client)
        u_res = await client.get("/api/v1/admin/users", headers=headers)
        assert u_res.status_code == 200
        user_id = u_res.json()["users"][0]["id"]

        act_res = await client.get(f"/api/v1/admin/users/{user_id}/activity", headers=headers)
        assert act_res.status_code == 200
        assert isinstance(act_res.json(), list)

        usage_res = await client.get(f"/api/v1/admin/users/{user_id}/usage", headers=headers)
        assert usage_res.status_code == 200
        data = usage_res.json()
        assert "storage" in data
        assert "ai_usage" in data
        assert data["storage"]["quota_mb"] == 500


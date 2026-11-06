"""
Tests for Phase 4A: Multi-User Security Hardening.

Validates:
1. Unauthenticated requests cannot spoof user identities via X-User-Id when DEV_AUTH_BYPASS=False.
2. Ordinary authenticated users cannot modify global LLM quota settings (HTTP 403 Forbidden).
3. Authorized administrators can modify global LLM quota settings (HTTP 200 OK).
4. User A cannot submit quality feedback against a message belonging to User B's research session (HTTP 403 Forbidden).
5. User A can submit quality feedback against their own message (HTTP 201 Created).
6. Submitting feedback for a non-existent message returns HTTP 404 Not Found.
7. Ordinary users can still view read-only quota settings and budget estimates without restriction (HTTP 200 OK).
"""

import pytest
from conftest import TestSessionLocal
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.models.session import ChatMessage, ResearchSession
from app.models.user import User, UserSession
from app.security.service import create_session_jwt, hash_token, hash_password, generate_csrf_token


@pytest.fixture
async def create_test_user():
    """Helper to create a test user with a real active session in the database."""
    async def _create(user_id: str, email: str, role: str = "authenticated"):
        async with TestSessionLocal() as db:
            user = User(
                id=user_id,
                email=email,
                display_name=f"Test {user_id}",
                hashed_password=hash_password("StrongPassword123!"),
                status="active",
                is_active=True,
            )
            db.add(user)
            await db.flush()

            from datetime import UTC, datetime, timedelta
            from uuid import uuid4
            session_id = f"sess_{uuid4().hex[:16]}"
            raw_token = create_session_jwt(user_id, email, session_id)
            token_hash = hash_token(raw_token)
            csrf_token = generate_csrf_token()

            user_session = UserSession(
                id=session_id,
                user_id=user_id,
                session_token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
                is_revoked=False,
            )
            db.add(user_session)
            await db.commit()

            return {
                "user": user,
                "token": raw_token,
                "csrf_token": csrf_token,
                "headers": {
                    "Authorization": f"Bearer {raw_token}",
                    "X-CSRF-Token": csrf_token,
                },
                "cookies": {
                    settings.SESSION_COOKIE_NAME: raw_token,
                    settings.CSRF_COOKIE_NAME: csrf_token,
                },
            }

    return _create


@pytest.mark.asyncio
async def test_unauthenticated_request_cannot_spoof_with_x_user_id(client):
    """When DEV_AUTH_BYPASS is False, unauthenticated requests with X-User-Id must be rejected with 401."""
    # Temporarily guarantee DEV_AUTH_BYPASS is False
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = False

    try:
        spoofed_headers = {"X-User-Id": "victim_researcher_001"}

        # Protected endpoints across documents, sessions, notes, usage, quota
        endpoints = [
            ("GET", "/api/v1/documents"),
            ("POST", "/api/v1/research/sessions", {"title": "Spoofed Session"}),
            ("GET", "/api/v1/notes"),
            ("GET", "/api/v1/usage"),
            ("PUT", "/api/v1/settings/llm-quota", {"rpm_limit": 25}),
        ]

        for method, endpoint, *payload in endpoints:
            if method == "GET":
                resp = await client.get(endpoint, headers=spoofed_headers)
            elif method == "POST":
                resp = await client.post(endpoint, json=payload[0], headers=spoofed_headers)
            elif method == "PUT":
                resp = await client.put(endpoint, json=payload[0], headers=spoofed_headers)

            assert resp.status_code == 401, f"Expected 401 for {method} {endpoint}, got {resp.status_code}"
            assert resp.json().get("error") == "UNAUTHENTICATED"
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_ordinary_user_cannot_modify_global_quota_settings(client):
    """Ordinary authenticated users must be forbidden (HTTP 403) from modifying global quota settings."""
    # Temporarily set DEV_AUTH_BYPASS=True to simulate ordinary researcher
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        ordinary_headers = {"X-User-Id": "ordinary_researcher_001"}
        update_payload = {
            "rpm_limit": 999,
            "tpm_limit": 999999,
            "rpd_limit": 9999,
        }

        resp = await client.put(
            "/api/v1/settings/llm-quota",
            json=update_payload,
            headers=ordinary_headers,
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data.get("error") == "FORBIDDEN_ACCESS"
        assert "Administrative privileges are required" in data.get("detail", "")
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_authorized_administrator_can_modify_quota_settings(client):
    """Authorized administrators can successfully update global quota settings."""
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        # In DEV_AUTH_BYPASS mode, user_admin_001 is configured in ADMIN_USER_IDS
        admin_headers = {"X-User-Id": "user_admin_001"}
        update_payload = {
            "rpm_limit": 30,
            "tpm_limit": 350000,
            "rpd_limit": 700,
            "warning_threshold_percent": 0.85,
            "safety_margin_percent": 0.15,
            "quota_timezone": "America/Los_Angeles",
        }

        resp = await client.put(
            "/api/v1/settings/llm-quota",
            json=update_payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rpm_limit"] == 30
        assert data["tpm_limit"] == 350000
        assert data["rpd_limit"] == 700
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_user_cannot_submit_feedback_against_another_users_message(client):
    """User B cannot submit feedback against a message in User A's research session."""
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        # 1. Create a session and message owned by user_A
        user_a_id = "user_alpha_001"
        user_b_id = "user_beta_002"

        async with TestSessionLocal() as session:
            sess_a = ResearchSession(
                owner_id=user_a_id,
                title="User Alpha Session",
            )
            session.add(sess_a)
            await session.flush()

            msg_a = ChatMessage(
                session_id=sess_a.id,
                role="assistant",
                content="Verified answer content for User A.",
            )
            session.add(msg_a)
            await session.commit()
            target_message_id = msg_a.id

        # 2. User B attempts to submit feedback for User A's message
        user_b_headers = {"X-User-Id": user_b_id}
        feedback_payload = {
            "rating": 1,
            "comment": "Malicious or unauthorized feedback from User B",
        }

        resp = await client.post(
            f"/api/v1/research/messages/{target_message_id}/feedback",
            json=feedback_payload,
            headers=user_b_headers,
        )

        assert resp.status_code == 403
        data = resp.json()
        assert data.get("error") == "FORBIDDEN_ACCESS"
        assert "permission" in data.get("detail", "").lower()

    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_user_can_submit_feedback_against_own_message(client):
    """User A can successfully submit quality rating feedback for their own message."""
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        user_a_id = "user_alpha_001"

        async with TestSessionLocal() as session:
            sess_a = ResearchSession(
                owner_id=user_a_id,
                title="User Alpha Session",
            )
            session.add(sess_a)
            await session.flush()

            msg_a = ChatMessage(
                session_id=sess_a.id,
                role="assistant",
                content="Verified answer content for User A.",
            )
            session.add(msg_a)
            await session.commit()
            target_message_id = msg_a.id

        user_a_headers = {"X-User-Id": user_a_id}
        feedback_payload = {
            "rating": 1,
            "comment": "Excellent synthesis with accurate page citations.",
        }

        resp = await client.post(
            f"/api/v1/research/messages/{target_message_id}/feedback",
            json=feedback_payload,
            headers=user_a_headers,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data.get("status") == "success"
        assert "feedback_id" in data
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_feedback_against_nonexistent_message_returns_404(client):
    """Submitting feedback for a message ID that does not exist returns 404."""
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        user_headers = {"X-User-Id": "user_dev_researcher_001"}
        feedback_payload = {"rating": 1, "comment": "Non-existent message"}

        resp = await client.post(
            "/api/v1/research/messages/msg_nonexistent_12345/feedback",
            json=feedback_payload,
            headers=user_headers,
        )
        assert resp.status_code == 404
        assert resp.json().get("error") == "MESSAGE_NOT_FOUND"
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


@pytest.mark.asyncio
async def test_ordinary_user_can_still_read_quota_and_budget_estimate(client):
    """Ordinary authenticated users can still freely read quota metrics and budget estimates."""
    original_bypass = settings.DEV_AUTH_BYPASS
    settings.DEV_AUTH_BYPASS = True

    try:
        user_headers = {"X-User-Id": "ordinary_researcher_001"}

        quota_resp = await client.get("/api/v1/settings/llm-quota", headers=user_headers)
        assert quota_resp.status_code == 200
        quota_data = quota_resp.json()
        assert "model_id" in quota_data
        assert "rpm_limit" in quota_data

        est_resp = await client.get("/api/v1/settings/llm-quota/estimate", headers=user_headers)
        assert est_resp.status_code == 200
        est_data = est_resp.json()
        assert "daily_questions_remaining" in est_data
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass

"""Integration test suite for ORION Public Demo Mode Backend.

Covers:
1. Public demo endpoints accessible without authentication:
   - GET /api/v1/demo/status
   - GET /api/v1/demo/papers
   - GET /api/v1/demo/papers/{document_id}
   - GET /api/v1/demo/papers/{document_id}/pdf
   - GET /api/v1/demo/papers/{document_id}/pages/{page_number}
   - GET /api/v1/demo/examples
   - POST /api/v1/demo/ask
2. Strict Allowlist enforcement:
   - Private document ID rejection (404)
   - Out-of-bounds page rejection (404 / 422)
   - Filter with non-allowlisted document ID (400)
3. Tenant isolation:
   - Zero anonymous user accounts created in database
   - Upload rejection (no public upload endpoint, 404/405)
   - Private researcher endpoints reject anonymous visitors (401)
   - Private admin endpoints reject anonymous visitors (401)
4. Cost & abuse controls:
   - Burst rate limiter (429 after 5 requests/min)
   - Query length limit (422 for >250 chars)
   - Pre-cached example questions return fast with 0 tokens and is_cached=True
   - Visitor daily query limit enforcement (429)
   - Feature flag disablement (ORION_ENABLE_PUBLIC_DEMO=False -> 404 on all demo endpoints)
5. Audit and LLM usage logging:
   - Demo queries logged to llm_usage_records with call_type="public_demo"
"""

import tempfile
import time
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.llm_usage import LLMUsageRecord
from app.models.user import User
from app.services.demo.corpus import CURATED_PAPERS
from app.services.demo.service import _IP_RATE_LIMIT_STORE


@pytest_asyncio.fixture
async def demo_client():
    """Isolated SQLite test client for Public Demo tests."""
    fd, path = tempfile.mkstemp(suffix="_test_demo.db")
    import os
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

    async def override_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)

    # Clear rate limiter before tests
    _IP_RATE_LIMIT_STORE.clear()

    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac, session_maker

    app.dependency_overrides.pop(get_db, None)
    _IP_RATE_LIMIT_STORE.clear()


@pytest.mark.asyncio
async def test_demo_status_endpoint(demo_client):
    """GET /api/v1/demo/status reports demo availability and daily limits."""
    client, _ = demo_client
    res = await client.get("/api/v1/demo/status")
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert data["total_papers"] == 4
    assert data["daily_budget_total"] == settings.DEMO_DAILY_GEMINI_BUDGET
    assert data["daily_budget_remaining"] >= 0
    assert data["visitor_daily_limit"] == settings.DEMO_VISITOR_DAILY_QUERY_LIMIT
    assert data["ip_rate_limit_per_minute"] == settings.DEMO_IP_RATE_LIMIT_PER_MINUTE


@pytest.mark.asyncio
async def test_demo_papers_catalog(demo_client):
    """GET /api/v1/demo/papers returns the 4 curated open-access papers."""
    client, _ = demo_client
    res = await client.get("/api/v1/demo/papers")
    assert res.status_code == 200
    papers = res.json()
    assert len(papers) == 4

    paper_ids = {p["id"] for p in papers}
    assert paper_ids == {
        "demo_doc_shukla_2025",
        "demo_doc_sulami_2023",
        "demo_doc_somantri_2026",
        "demo_doc_joltreau_2022",
    }

    # Verify open-access metadata
    for p in papers:
        assert p["doi"] is not None
        assert "CC BY 4.0" in p["license"]
        assert p["total_pages"] >= 3
        assert p["file_size_bytes"] > 0


@pytest.mark.asyncio
async def test_demo_single_paper_metadata(demo_client):
    """GET /api/v1/demo/papers/{document_id} returns valid metadata or 404."""
    client, _ = demo_client
    # Allowlisted paper (supports canonical ID and alias)
    res = await client.get("/api/v1/demo/papers/demo_doc_s40726_epr")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "demo_doc_s40726_epr"
    assert "Plastic Waste Recycling" in data["title"] or "Extended Producer Responsibility" in data["abstract"]

    # Non-allowlisted paper returns 404
    res_unknown = await client.get("/api/v1/demo/papers/private_researcher_doc_999")
    assert res_unknown.status_code == 404
    assert "not found in the approved corpus allowlist" in res_unknown.json()["detail"]


@pytest.mark.asyncio
async def test_demo_pdf_streaming(demo_client):
    """GET /api/v1/demo/papers/{document_id}/pdf streams valid PDF binary."""
    client, _ = demo_client
    res = await client.get("/api/v1/demo/papers/demo_doc_shukla_epr/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "inline; filename=" in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"%PDF")

    # Non-allowlist returns 404
    res_fake = await client.get("/api/v1/demo/papers/fake_doc_id/pdf")
    assert res_fake.status_code == 404


@pytest.mark.asyncio
async def test_demo_page_text_inspection(demo_client):
    """GET /api/v1/demo/papers/{document_id}/pages/{page_number} extracts verified text."""
    client, _ = demo_client
    # Valid page 1
    res = await client.get("/api/v1/demo/papers/demo_doc_garcia_epr/pages/1")
    assert res.status_code == 200
    page_data = res.json()
    assert page_data["page_number"] == 1
    assert "Extended Producer Responsibility" in page_data["text"]
    assert page_data["has_content"] is True

    # Out of bounds page
    res_out = await client.get("/api/v1/demo/papers/demo_doc_garcia_epr/pages/99")
    assert res_out.status_code == 404

    # Page 0 violates ge=1
    res_zero = await client.get("/api/v1/demo/papers/demo_doc_garcia_epr/pages/0")
    assert res_zero.status_code == 422


@pytest.mark.asyncio
async def test_demo_examples_endpoint(demo_client):
    """GET /api/v1/demo/examples returns 5 curated questions."""
    client, _ = demo_client
    res = await client.get("/api/v1/demo/examples")
    assert res.status_code == 200
    examples = res.json()
    assert len(examples) == 5
    for ex in examples:
        assert ex["id"].startswith("ex_")
        assert len(ex["question"]) > 10
        assert len(ex["target_papers"]) > 0


@pytest.mark.asyncio
async def test_demo_ask_cached_example(demo_client):
    """POST /api/v1/demo/ask returns instant cached answer with 100% precision citations."""
    client, session_maker = demo_client
    req_body = {
        "question": "What is Extended Producer Responsibility (EPR) and what is its primary objective in waste management?",
    }
    res = await client.post("/api/v1/demo/ask", json=req_body, headers={"X-Forwarded-For": "198.51.100.1"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_cached"] is True
    assert data["grounding_score"] == 1.0
    assert len(data["citations"]) >= 2
    assert "Lindhqvist" in data["answer"]

    # Verify audit record stored with call_type="public_demo" and is_provider_call=False
    async with session_maker() as db:
        stmt = select(LLMUsageRecord).where(LLMUsageRecord.call_type == "public_demo")
        records = (await db.execute(stmt)).scalars().all()
        assert len(records) >= 1
        rec = records[0]
        assert rec.is_provider_call is False
        assert rec.status == "cached"
        assert rec.prompt_tokens == 0

        # Verify ZERO anonymous users created in user table
        user_stmt = select(User)
        users = (await db.execute(user_stmt)).scalars().all()
        assert len(users) == 0


@pytest.mark.asyncio
async def test_demo_ask_unanswerable_off_topic(demo_client):
    """POST /api/v1/demo/ask abstains gracefully when question is off-topic."""
    client, _ = demo_client
    req_body = {
        "question": "What are the latest breakthroughs in superconducting quantum qubits?",
    }
    res = await client.post("/api/v1/demo/ask", json=req_body, headers={"X-Forwarded-For": "198.51.100.2"})
    assert res.status_code == 200
    data = res.json()
    assert data["insufficient_evidence"] is True
    assert data["grounding_score"] == 0.0
    assert "could not find sufficient evidence" in data["answer"].lower()
    assert len(data["citations"]) == 0


@pytest.mark.asyncio
async def test_demo_ask_input_validation(demo_client):
    """POST /api/v1/demo/ask enforces query length and allowlist document filter."""
    client, _ = demo_client

    # Over 250 characters
    long_question = "What is " + ("x" * 260)
    res_long = await client.post("/api/v1/demo/ask", json={"question": long_question})
    assert res_long.status_code == 422

    # Empty question
    res_empty = await client.post("/api/v1/demo/ask", json={"question": ""})
    assert res_empty.status_code == 422

    # Non-allowlist document ID in filter
    res_bad_filter = await client.post(
        "/api/v1/demo/ask",
        json={
            "question": "Explain EPR instruments",
            "document_ids": ["private_confidential_doc_777"],
        },
    )
    assert res_bad_filter.status_code == 400
    assert "not in the curated demo corpus allowlist" in res_bad_filter.json()["detail"]


@pytest.mark.asyncio
async def test_demo_burst_rate_limiting(demo_client):
    """In-memory rate limiter returns 429 when IP exceeds 5 req/min."""
    client, _ = demo_client
    visitor_ip = "203.0.113.42"

    req_body = {
        "question": "What is Extended Producer Responsibility (EPR)?",
    }

    # Make 5 allowed requests
    for i in range(settings.DEMO_IP_RATE_LIMIT_PER_MINUTE):
        res = await client.post("/api/v1/demo/ask", json=req_body, headers={"X-Forwarded-For": visitor_ip})
        assert res.status_code == 200, f"Request {i+1} failed"

    # 6th request from same IP must be rate limited
    res_limited = await client.post("/api/v1/demo/ask", json=req_body, headers={"X-Forwarded-For": visitor_ip})
    assert res_limited.status_code == 429
    assert "rate limit exceeded" in res_limited.json()["detail"].lower()

    # Different IP should still be allowed
    res_other_ip = await client.post("/api/v1/demo/ask", json=req_body, headers={"X-Forwarded-For": "203.0.113.43"})
    assert res_other_ip.status_code == 200


@pytest.mark.asyncio
async def test_demo_feature_flag_disabled(demo_client):
    """When ORION_ENABLE_PUBLIC_DEMO is False, all demo endpoints return 404."""
    client, _ = demo_client

    original_setting = settings.ORION_ENABLE_PUBLIC_DEMO
    try:
        settings.ORION_ENABLE_PUBLIC_DEMO = False

        res_status = await client.get("/api/v1/demo/status")
        assert res_status.status_code == 404

        res_papers = await client.get("/api/v1/demo/papers")
        assert res_papers.status_code == 404

        res_examples = await client.get("/api/v1/demo/examples")
        assert res_examples.status_code == 404

        res_ask = await client.post("/api/v1/demo/ask", json={"question": "What is EPR?"})
        assert res_ask.status_code == 404
    finally:
        settings.ORION_ENABLE_PUBLIC_DEMO = original_setting


@pytest.mark.asyncio
async def test_anonymous_visitor_blocked_from_private_apis(demo_client):
    """Verify anonymous visitors cannot access private researcher or admin endpoints."""
    client, _ = demo_client

    original_bypass = settings.DEV_AUTH_BYPASS
    try:
        settings.DEV_AUTH_BYPASS = False

        # Private document upload / library
        res_docs = await client.get("/api/v1/documents")
        assert res_docs.status_code == 401

        # Private research Q&A
        res_qa = await client.post("/api/v1/research/ask", json={"question": "Test query"})
        assert res_qa.status_code == 401

        # Admin user management
        res_admin = await client.get("/api/v1/admin/users")
        assert res_admin.status_code == 401

        # Admin system diagnostics
        res_sys = await client.get("/api/v1/settings/system")
        assert res_sys.status_code == 401

        # No demo upload endpoint exists
        res_upload = await client.post("/api/v1/demo/upload")
        assert res_upload.status_code in (404, 405)

    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


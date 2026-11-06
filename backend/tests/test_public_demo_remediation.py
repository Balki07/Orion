"""Remediation validation tests for ORION Public Demo Phase 4.

Verifies:
1. Trusted Client IP Resolution and anti-spoofing header handling.
2. Distributed sliding window rate limiting across simulated parallel workers.
3. Concurrency-safe atomic Gemini daily budget reservation, boundary enforcement, and failure release.
4. Verified CC BY 4.0 paper catalog metadata, DOI integrity, and PDF streaming security headers (X-Frame-Options: SAMEORIGIN).
"""

import asyncio
from datetime import UTC, datetime, timedelta
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.llm_usage import LLMUsageRecord
from app.security.ip_resolver import get_trusted_client_ip
from app.services.demo.corpus import CURATED_PAPERS, ID_ALIASES, demo_corpus_service
from app.services.demo.service import (
    _IP_RATE_LIMIT_STORE,
    check_and_reserve_rate_limit,
    demo_service,
    get_daily_demo_provider_call_count,
    get_visitor_session_id,
    try_reserve_gemini_budget,
)


@pytest_asyncio.fixture
async def remediation_db():
    """Isolated SQLite test database for remediation validation."""
    fd, path = tempfile.mkstemp(suffix="_remediation.db")
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
    _IP_RATE_LIMIT_STORE.clear()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_maker

    app.dependency_overrides.pop(get_db, None)
    _IP_RATE_LIMIT_STORE.clear()


# ==============================================================================
# Task 3: Trusted Client IP Resolution Tests
# ==============================================================================

def test_trusted_client_ip_render_true_client_ip():
    """True-Client-IP header (provided by Render) takes precedence over forged X-Forwarded-For."""
    scope = {
        "type": "http",
        "headers": [
            (b"true-client-ip", b"198.51.100.99"),
            (b"x-forwarded-for", b"1.1.1.1, 2.2.2.2"),
        ],
        "client": ("10.0.0.1", 12345),
    }
    req = Request(scope)
    ip = get_trusted_client_ip(req)
    assert ip == "198.51.100.99"


def test_trusted_client_ip_cf_connecting_ip():
    """CF-Connecting-IP header is prioritized for Cloudflare proxies."""
    scope = {
        "type": "http",
        "headers": [
            (b"cf-connecting-ip", b"203.0.113.88"),
            (b"x-forwarded-for", b"3.3.3.3"),
        ],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    ip = get_trusted_client_ip(req)
    assert ip == "203.0.113.88"


def test_trusted_client_ip_x_forwarded_for_spoofing_defense():
    """Traversing X-Forwarded-For selects the rightmost untrusted public client IP."""
    scope = {
        "type": "http",
        "headers": [
            # Attacker prepends fake IP '8.8.8.8', proxy appends real client '198.51.100.42'
            (b"x-forwarded-for", b"8.8.8.8, 198.51.100.42"),
        ],
        "client": ("10.0.0.5", 54321),
    }
    req = Request(scope)
    ip = get_trusted_client_ip(req)
    assert ip == "198.51.100.42"


def test_trusted_client_ip_fallback_to_socket():
    """When proxy headers are missing, falls back cleanly to socket client host."""
    scope = {
        "type": "http",
        "headers": [],
        "client": ("192.0.2.15", 8080),
    }
    req = Request(scope)
    ip = get_trusted_client_ip(req)
    assert ip == "192.0.2.15"


# ==============================================================================
# Task 2: Distributed Rate Limiting Across Parallel Workers
# ==============================================================================

@pytest.mark.asyncio
async def test_distributed_burst_rate_limiting(remediation_db):
    """Parallel requests from the same visitor IP enforce the 5 req/min limit across workers."""
    client, session_maker = remediation_db
    visitor_ip = "198.51.100.77"
    req_body = {"question": "What is Extended Producer Responsibility (EPR)?"}

    # First 5 requests must succeed
    for i in range(5):
        res = await client.post(
            "/api/v1/demo/ask",
            json=req_body,
            headers={"True-Client-IP": visitor_ip},
        )
        assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}"

    # 6th request within 60s window must be rejected with 429
    res_burst = await client.post(
        "/api/v1/demo/ask",
        json=req_body,
        headers={"True-Client-IP": visitor_ip},
    )
    assert res_burst.status_code == 429
    assert "rate limit exceeded" in res_burst.json()["detail"].lower()

    # Verify that in-flight records were persisted to LLMUsageRecord
    async with session_maker() as session:
        session_id = get_visitor_session_id(visitor_ip)
        stmt = select(func.count(LLMUsageRecord.id)).where(
            LLMUsageRecord.call_type == "public_demo",
            LLMUsageRecord.session_id == session_id,
        )
        res = await session.execute(stmt)
        count = res.scalar()
        assert count == 5


# ==============================================================================
# Task 4: Atomic Gemini Daily Budget Reservation & Concurrency Race Safety
# ==============================================================================

@pytest.mark.asyncio
async def test_atomic_budget_reservation_boundary(remediation_db):
    """When budget is near the limit, exactly the remaining slots are reserved and excess requests fall back."""
    _, session_maker = remediation_db
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with session_maker() as session:
        # Pre-seed records such that exactly 1 slot remains
        remaining_budget = 1
        preseed_count = settings.DEMO_DAILY_GEMINI_BUDGET - remaining_budget

        for i in range(preseed_count):
            rec = LLMUsageRecord(
                trace_id=f"preseed_{i}",
                session_id=f"seed_session_{i}",
                call_type="public_demo",
                model=settings.GEMINI_MODEL,
                attempt_number=1,
                max_attempts=1,
                is_provider_call=True,
                status="success",
                http_status_code=200,
                created_at=today_start + timedelta(minutes=i % 60),
            )
            session.add(rec)
        await session.commit()

        # Verify current count is preseed_count
        count = await get_daily_demo_provider_call_count(session)
        assert count == preseed_count

        # Simulate 5 concurrent reservation attempts
        records = [
            LLMUsageRecord(
                trace_id=f"concurrent_test_{j}",
                session_id=f"concurrent_sess_{j}",
                call_type="public_demo",
                model="orion-demo",
                attempt_number=1,
                max_attempts=1,
                is_provider_call=False,
                status="in_flight",
            )
            for j in range(5)
        ]
        for r in records:
            session.add(r)
        await session.commit()

        async def attempt_reserve(r):
            async with session_maker() as s:
                # Merge row into new session to simulate parallel worker tasks
                r_local = await s.get(LLMUsageRecord, r.id)
                return await try_reserve_gemini_budget(s, r_local)

        results = await asyncio.gather(*(attempt_reserve(r) for r in records))

        # Exactly 1 reservation must succeed (True), and exactly 4 must fail (False)
        assert results.count(True) == 1
        assert results.count(False) == 4

        # Total provider calls + active reservations must exactly equal budget
        final_count = await get_daily_demo_provider_call_count(session)
        assert final_count == settings.DEMO_DAILY_GEMINI_BUDGET


@pytest.mark.asyncio
async def test_budget_reservation_release_on_failure(remediation_db):
    """When a provider call fails, the reservation is released and not counted against daily budget."""
    _, session_maker = remediation_db

    async with session_maker() as session:
        initial_count = await get_daily_demo_provider_call_count(session)

        # Acquire a reservation
        usage_rec = LLMUsageRecord(
            trace_id="test_release_trace",
            session_id="test_release_session",
            call_type="public_demo",
            model=settings.GEMINI_MODEL,
            attempt_number=1,
            max_attempts=1,
            is_provider_call=False,
            status="in_flight",
        )
        session.add(usage_rec)
        await session.commit()

        reserved = await try_reserve_gemini_budget(session, usage_rec)
        assert reserved is True

        # Count while reserved increases by 1
        count_during_reservation = await get_daily_demo_provider_call_count(session)
        assert count_during_reservation == initial_count + 1

        # Simulate call failure: release reservation
        usage_rec.status = "failed"
        usage_rec.is_provider_call = False
        usage_rec.error_detail = "Simulated Gemini 503 Service Unavailable"
        await session.commit()

        # Count after release returns to initial count
        count_after_release = await get_daily_demo_provider_call_count(session)
        assert count_after_release == initial_count


# ==============================================================================
# Task 1 & Task 5: CC BY 4.0 Metadata & PDF Security Headers
# ==============================================================================

@pytest.mark.asyncio
async def test_cc_by_4_paper_metadata_and_doi_integrity():
    """All 4 curated papers have verified CC BY 4.0 licenses and valid academic DOIs."""
    catalog = demo_corpus_service.list_papers()
    assert len(catalog) == 4

    # Verify no duplicates
    titles = [p.title for p in catalog]
    assert len(set(titles)) == 4

    dois = [p.doi for p in catalog]
    assert len(set(dois)) == 4

    for paper in catalog:
        assert "CC BY 4.0" in paper.license
        assert paper.doi.startswith("10.")
        assert paper.authors is not None and len(paper.authors) > 5
        assert paper.year in (2022, 2023, 2025, 2026)


@pytest.mark.asyncio
async def test_pdf_streaming_security_headers(remediation_db):
    """PDF streaming endpoint sets X-Frame-Options: SAMEORIGIN and CSP frame-ancestors 'self'."""
    client, _ = remediation_db

    for doc_id in ("demo_doc_s40726_epr", "demo_doc_shukla_epr", "demo_doc_somantri_epr", "demo_doc_garcia_epr"):
        res = await client.get(f"/api/v1/demo/papers/{doc_id}/pdf")
        assert res.status_code == 200
        assert res.headers["x-frame-options"] == "SAMEORIGIN"
        assert "frame-ancestors 'self'" in res.headers.get("content-security-policy", "")
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_descriptive_aliases_resolution(remediation_db):
    """Descriptive aliases map seamlessly to authentic paper metadata and PDFs."""
    client, _ = remediation_db

    aliases = {
        "demo_doc_shukla_2025": "s40726-025-00392-4.pdf",
        "demo_doc_sulami_2023": "sulami-2023-packaging-epr.pdf",
        "demo_doc_somantri_2026": "isi_31.07_22.pdf",
        "demo_doc_joltreau_2022": "joltreau-2022-packaging-epr.pdf",
    }

    for alias, expected_filename in aliases.items():
        res = await client.get(f"/api/v1/demo/papers/{alias}")
        assert res.status_code == 200
        data = res.json()
        assert data["filename"] == expected_filename

        res_pdf = await client.get(f"/api/v1/demo/papers/{alias}/pdf")
        assert res_pdf.status_code == 200
        assert res_pdf.content.startswith(b"%PDF")


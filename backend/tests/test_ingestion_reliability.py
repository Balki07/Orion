"""Comprehensive Ingestion Reliability and PDF Edge-Case Test Suite for Phase 6A.

Covers:
1. Single upload triggers only one ingestion job dispatch (no duplicate BackgroundTasks).
2. Two concurrent workers cannot claim the same document (atomic claiming).
3. Scanned / image-only PDF is marked as failed, not completed.
4. Encrypted / password-protected PDF is rejected with ERR_PDF_ENCRYPTED.
5. Corrupted PDF is handled safely with ERR_PDF_CORRUPT.
6. Empty extraction never produces a false successful document.
7. A stuck job past timeout is detected and recovered by the watchdog.
8. A legitimately active job within timeout is not incorrectly recovered.
9. Retrying ingestion deletes old chunks and prevents duplicates.
10. Multi-user document isolation and ownership checks remain strictly intact.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_storage_service
from app.core.config import settings
from app.core.errors import IngestionError, OrionException
from app.db.base import Base
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.ingestion.extractor import PdfExtractor
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.worker import DurableIngestionWorker, get_ingestion_worker
from app.services.storage.local import LocalStorageService


def make_text_pdf(text: str = "Valid technical paper explaining semantic retrieval.") -> bytes:
    """Create a minimal digitally formatted text-based PDF."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_encrypted_pdf(user_pw: str = "secret123", owner_pw: str = "admin123") -> bytes:
    """Create an AES-256 password-protected PDF."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Confidential academic manuscript")
    pdf_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=user_pw,
        owner_pw=owner_pw,
    )
    doc.close()
    return pdf_bytes


def make_scanned_image_pdf() -> bytes:
    """Create a scanned-like PDF containing only vector graphics and zero text."""
    doc = pymupdf.open()
    page = doc.new_page()
    # Draw gray rectangle simulating a scanned document page without OCR layer
    page.draw_rect(pymupdf.Rect(50, 50, 300, 400), color=(0.2, 0.2, 0.2), fill=(0.9, 0.9, 0.9))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_corrupt_pdf() -> bytes:
    """Create a corrupted PDF payload with valid header but unparseable body."""
    return b"%PDF-1.5\n%%EOF\x00\xff\xfe corrupted binary stream garbage"


@pytest.fixture
async def setup_test_env(tmp_path):
    """Sets up an isolated SQLite test database and local storage backend."""
    test_db_url = f"sqlite+aiosqlite:///{tmp_path}/test_ingestion_rel.db"
    test_engine = create_async_engine(test_db_url, connect_args={"check_same_thread": False})
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    local_storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    def override_get_storage():
        return local_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_get_storage

    yield TestSessionLocal, local_storage

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_01_upload_triggers_only_durable_worker(setup_test_env):
    """Requirement 1: Verify document upload triggers only the durable worker, not BackgroundTasks."""
    TestSessionLocal, local_storage = setup_test_env
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register user
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "worker_test@orion.ai", "password": "Password123!#", "display_name": "Worker Tester"},
        )
        assert reg.status_code == 201
        async with TestSessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == "worker_test@orion.ai"))).scalar_one()
            user.access_status = "active"
            await session.commit()
        token = reg.json()["access_token"]
        csrf = reg.json()["csrf_token"]
        headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}

        worker = get_ingestion_worker()
        with patch.object(worker, "trigger") as mock_worker_trigger:
            pdf_bytes = make_text_pdf("Sample text for single trigger verification.")
            res = await client.post(
                "/api/v1/documents",
                files={"file": ("single_dispatch.pdf", pdf_bytes, "application/pdf")},
                headers=headers,
            )
            assert res.status_code == 201
            assert res.json()["status"] == "queued"
            # Exactly one authoritative worker trigger
            assert mock_worker_trigger.call_count == 1


@pytest.mark.asyncio
async def test_02_concurrent_workers_cannot_claim_same_document(setup_test_env):
    """Requirement 2: Two concurrent worker workers cannot claim the same queued document."""
    TestSessionLocal, local_storage = setup_test_env

    async with TestSessionLocal() as session:
        doc = Document(
            id="doc_claim_race_test",
            owner_id="usr_tester_1",
            filename="race.pdf",
            storage_key="usr_tester_1/doc_claim_race_test/race.pdf",
            content_hash="hash123",
            file_size=1024,
            status="queued",
        )
        session.add(doc)
        await session.commit()

    worker_a = DurableIngestionWorker()
    worker_b = DurableIngestionWorker()

    # Mock process_document so worker claims without long pipeline execution
    worker_a._pipeline = AsyncMock()
    worker_a._pipeline.process_document = AsyncMock(return_value=None)
    worker_b._pipeline = AsyncMock()
    worker_b._pipeline.process_document = AsyncMock(return_value=None)

    # Patch AsyncSessionLocal in worker module to use our test session
    with patch("app.services.ingestion.worker.AsyncSessionLocal", TestSessionLocal):
        # Worker A claims and processes
        claimed_a = await worker_a.process_next_job()
        assert claimed_a is True

        # Worker B tries to claim immediately - should find no queued documents
        claimed_b = await worker_b.process_next_job()
        assert claimed_b is False


@pytest.mark.asyncio
async def test_03_scanned_pdf_marked_failed_not_completed(setup_test_env):
    """Requirement 3: Scanned/image-only PDF fails extraction with ERR_PDF_SCANNED_NO_TEXT."""
    TestSessionLocal, local_storage = setup_test_env
    pdf_bytes = make_scanned_image_pdf()

    extractor = PdfExtractor(max_pages=50)
    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_from_bytes(pdf_bytes, filename="scanned.pdf")

    assert exc_info.value.error_code == "ERR_PDF_SCANNED_NO_TEXT"
    assert "OCR is not currently supported" in exc_info.value.detail


@pytest.mark.asyncio
async def test_04_encrypted_pdf_rejected_with_error(setup_test_env):
    """Requirement 4: Encrypted/password-protected PDF is detected before extraction and rejected."""
    TestSessionLocal, local_storage = setup_test_env
    pdf_bytes = make_encrypted_pdf(user_pw="locked123")

    extractor = PdfExtractor(max_pages=50)
    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_from_bytes(pdf_bytes, filename="encrypted.pdf")

    assert exc_info.value.error_code == "ERR_PDF_ENCRYPTED"
    assert "password-protected or encrypted" in exc_info.value.detail


@pytest.mark.asyncio
async def test_05_corrupted_pdf_handled_safely(setup_test_env):
    """Requirement 5: Corrupted PDF does not crash the server and raises ERR_PDF_CORRUPT."""
    TestSessionLocal, local_storage = setup_test_env
    pdf_bytes = make_corrupt_pdf()

    extractor = PdfExtractor(max_pages=50)
    with pytest.raises(IngestionError) as exc_info:
        extractor.extract_from_bytes(pdf_bytes, filename="corrupt.pdf")

    assert exc_info.value.error_code == "ERR_PDF_CORRUPT"


@pytest.mark.asyncio
async def test_06_empty_extraction_never_creates_false_success(setup_test_env):
    """Requirement 6: Ingestion pipeline fails and persists failure if extraction yields zero text chunks."""
    TestSessionLocal, local_storage = setup_test_env
    pipeline = IngestionPipeline()
    pipeline.storage = local_storage

    doc_id = "doc_scanned_pipeline_test"
    user_id = "usr_scanned_001"
    storage_key = f"{user_id}/{doc_id}/scanned.pdf"
    scanned_bytes = make_scanned_image_pdf()
    await local_storage.save_file(scanned_bytes, storage_key)

    async with TestSessionLocal() as session:
        doc = Document(
            id=doc_id,
            owner_id=user_id,
            filename="scanned.pdf",
            storage_key=storage_key,
            content_hash="scanned_hash",
            file_size=len(scanned_bytes),
            status="queued",
        )
        session.add(doc)
        await session.commit()

        # Execute pipeline
        with pytest.raises(IngestionError):
            await pipeline.process_document(doc_id, session)

        # Verify document is failed, not completed
        refreshed = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert refreshed.status == "failed"
        assert "OCR is not currently supported" in refreshed.processing_error
        assert "error_code=ERR_PDF_SCANNED_NO_TEXT" in refreshed.extraction_warnings

        # Verify zero chunks created
        chunk_count = (await session.execute(select(func.count(Chunk.id)).where(Chunk.document_id == doc_id))).scalar()
        assert chunk_count == 0


@pytest.mark.asyncio
async def test_07_stuck_job_detected_and_recovered_by_watchdog(setup_test_env):
    """Requirement 7: A job stuck in an active state beyond timeout is detected and re-queued by watchdog."""
    TestSessionLocal, local_storage = setup_test_env
    worker = DurableIngestionWorker()

    doc_id = "doc_stuck_test_01"
    user_id = "usr_watchdog_001"

    async with TestSessionLocal() as session:
        watchdog_owner = User(
            id=user_id,
            email="watchdog@orion.ai",
            display_name="Watchdog Owner",
            hashed_password="dummy_hash",
            role="researcher",
            access_status="active",
            status="active",
            is_active=True,
        )
        session.add(watchdog_owner)
        await session.commit()

        doc = Document(
            id=doc_id,
            owner_id=user_id,
            filename="stuck.pdf",
            storage_key=f"{user_id}/{doc_id}/stuck.pdf",
            content_hash="stuck_hash",
            file_size=2048,
            status="embedding",  # Active interim state
        )
        session.add(doc)
        await session.commit()

        # Manually backdate updated_at to simulate stuck timeout
        stale_time = datetime.now(UTC) - timedelta(seconds=settings.INGESTION_STUCK_TIMEOUT_SECONDS + 30)
        doc.updated_at = stale_time
        await session.commit()

        # Run watchdog
        stuck_count = await worker.recover_stuck_jobs(session)
        assert stuck_count == 1

        refreshed = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert refreshed.status == "queued"
        assert "re-queued by watchdog" in refreshed.processing_error
        assert any("retry_count=1" in w for w in refreshed.extraction_warnings)


@pytest.mark.asyncio
async def test_08_active_job_within_timeout_not_recovered(setup_test_env):
    """Requirement 8: A legitimately active job within the timeout window is NOT touched by watchdog."""
    TestSessionLocal, local_storage = setup_test_env
    worker = DurableIngestionWorker()

    doc_id = "doc_active_legit_test"
    user_id = "usr_watchdog_002"

    async with TestSessionLocal() as session:
        doc = Document(
            id=doc_id,
            owner_id=user_id,
            filename="active.pdf",
            storage_key=f"{user_id}/{doc_id}/active.pdf",
            content_hash="active_hash",
            file_size=2048,
            status="embedding",  # Active state, updated just now
        )
        session.add(doc)
        await session.commit()

        # Run watchdog
        stuck_count = await worker.recover_stuck_jobs(session)
        assert stuck_count == 0

        refreshed = (await session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert refreshed.status == "embedding"  # Preserved without interference


@pytest.mark.asyncio
async def test_09_retrying_ingestion_does_not_duplicate_chunks(setup_test_env):
    """Requirement 9: Ingestion retry deletes old chunks atomically to avoid chunk duplication."""
    TestSessionLocal, local_storage = setup_test_env
    pipeline = IngestionPipeline()
    pipeline.storage = local_storage

    doc_id = "doc_retry_dedup_test"
    user_id = "usr_dedup_001"
    storage_key = f"{user_id}/{doc_id}/paper.pdf"
    valid_pdf = make_text_pdf("First run of scientific research content for quantum computation.")
    await local_storage.save_file(valid_pdf, storage_key)

    async with TestSessionLocal() as session:
        doc = Document(
            id=doc_id,
            owner_id=user_id,
            filename="paper.pdf",
            storage_key=storage_key,
            content_hash="valid_hash_1",
            file_size=len(valid_pdf),
            status="queued",
        )
        session.add(doc)
        await session.commit()

        # Run 1: Successful completion
        await pipeline.process_document(doc_id, session)

        chunks_run_1 = (await session.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        count_1 = len(chunks_run_1)
        assert count_1 > 0

        # Run 2: Retry processing the exact same document
        await pipeline.process_document(doc_id, session)

        chunks_run_2 = (await session.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        count_2 = len(chunks_run_2)

        # Chunk count must be identical, not doubled
        assert count_2 == count_1


@pytest.mark.asyncio
async def test_10_multi_user_document_isolation_intact(setup_test_env):
    """Requirement 10: User B cannot retry or inspect User A's document."""
    TestSessionLocal, local_storage = setup_test_env
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register User A
        reg_a = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner_a@orion.ai", "password": "Password123!#", "display_name": "User A"},
        )
        token_a = reg_a.json()["access_token"]
        csrf_a = reg_a.json()["csrf_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-CSRF-Token": csrf_a}

        # Register User B
        reg_b = await client.post(
            "/api/v1/auth/register",
            json={"email": "intruder_b@orion.ai", "password": "Password123!#", "display_name": "User B"},
        )
        token_b = reg_b.json()["access_token"]
        csrf_b = reg_b.json()["csrf_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-CSRF-Token": csrf_b}

        # Activate User A and User B in test DB so they are active researchers
        async with TestSessionLocal() as session:
            user_a = (await session.execute(select(User).where(User.email == "owner_a@orion.ai"))).scalar_one()
            user_a.access_status = "active"
            user_b = (await session.execute(select(User).where(User.email == "intruder_b@orion.ai"))).scalar_one()
            user_b.access_status = "active"
            await session.commit()

        # User A uploads a document
        pdf_bytes = make_text_pdf("Document belonging strictly to User A.")
        up = await client.post(
            "/api/v1/documents",
            files={"file": ("user_a_doc.pdf", pdf_bytes, "application/pdf")},
            headers=headers_a,
        )
        doc_id = up.json()["id"]

        # User B attempts to access User A's status -> 403 Forbidden
        status_b = await client.get(f"/api/v1/documents/{doc_id}/status", headers=headers_b)
        assert status_b.status_code == 403

        # User B attempts to retry User A's document -> 403 Forbidden
        retry_b = await client.post(f"/api/v1/documents/{doc_id}/retry", headers=headers_b)
        assert retry_b.status_code == 403


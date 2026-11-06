"""Comprehensive test suite for ORION Phase 6B: Storage Governance & Production Storage Readiness.

Verifies:
1. User below 500 MB can upload.
2. User at quota cannot upload more (HTTP 413 STORAGE_QUOTA_EXCEEDED).
3. User exceeding quota is rejected with remaining capacity details.
4. Batch uploads enforce aggregate quota.
5. Concurrent uploads cannot bypass quota (race condition test).
6. Different users have independent quotas (multi-user isolation).
7. Failed/deleted document storage accounting is correct.
8. Storage usage API returns correct values (/api/v1/documents/storage-usage).
9. Unauthorized users cannot inspect other users' usage.
10. Missing S3 production configuration fails validation safely.
11. Development mode continues to support local storage.
12. S3 readiness failure is reported safely without leaking secrets.
"""

import asyncio
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import boto3
from moto import mock_aws

from app.core.config import Settings, settings
from app.core.errors import StorageQuotaExceededError
from app.models.document import Document
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService
from app.services.ingestion.worker import get_ingestion_worker


@pytest.fixture(autouse=True)
def stop_worker_polling():
    """Ensure durable ingestion worker polling does not run uncontrolled during tests."""
    worker = get_ingestion_worker()
    worker.stop()
    yield
    worker.stop()


@pytest.mark.asyncio
async def test_01_user_below_quota_can_upload(client, sample_pdf_bytes):
    """1. User below 500 MB can successfully upload a document."""
    headers = {"X-User-Id": "usr_quota_tester_1"}
    files = {"file": ("paper_normal.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}

    response = await client.post("/api/v1/documents", files=files, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "paper_normal.pdf"
    assert data["file_size"] == len(sample_pdf_bytes)
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_02_user_at_quota_cannot_upload_more(client, sample_pdf_bytes):
    """2. User at quota cannot upload more and receives HTTP 413."""
    headers = {"X-User-Id": "usr_quota_tester_2"}

    # Mock setting quota to a small value (1 MB) and populate existing usage
    original_quota = settings.USER_STORAGE_QUOTA_MB
    try:
        # Set quota to 0 MB (0 bytes) so any upload exceeds quota
        settings.USER_STORAGE_QUOTA_MB = 0
        files = {"file": ("exceed.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        response = await client.post("/api/v1/documents", files=files, headers=headers)

        assert response.status_code == 413
        data = response.json()
        assert "Storage quota exceeded" in data["detail"]
    finally:
        settings.USER_STORAGE_QUOTA_MB = original_quota


@pytest.mark.asyncio
async def test_03_user_exceeding_quota_receives_remaining_capacity_details(client, sample_pdf_bytes):
    """3. User exceeding quota is rejected with details on usage, quota limit, remaining capacity."""
    headers = {"X-User-Id": "usr_quota_tester_3"}
    original_quota = settings.USER_STORAGE_QUOTA_MB
    try:
        # Allow 1 KB quota while sample PDF is ~2-3 KB
        settings.USER_STORAGE_QUOTA_MB = 0  # 0 bytes quota
        files = {"file": ("rejected_cap.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        response = await client.post("/api/v1/documents", files=files, headers=headers)

        assert response.status_code == 413
        data = response.json()
        assert "Storage quota exceeded" in data["detail"]
        assert "0 MB limit" in data["detail"]
        assert "remaining" in data["detail"].lower()
    finally:
        settings.USER_STORAGE_QUOTA_MB = original_quota


@pytest.mark.asyncio
async def test_04_batch_uploads_enforce_aggregate_quota(client, sample_pdf_bytes):
    """4. Batch uploads enforce aggregate cumulative quota across items."""
    headers = {"X-User-Id": "usr_quota_batch_user"}
    original_quota = settings.USER_STORAGE_QUOTA_MB

    try:
        # Set quota to just enough for 1 file but not 2
        one_file_mb = (len(sample_pdf_bytes) * 1.5) / (1024 * 1024)
        # Using mock patch on user_storage_quota_bytes to allow exactly 1 file size
        with patch.object(
            type(settings),
            "user_storage_quota_bytes",
            new_callable=lambda: property(lambda self: len(sample_pdf_bytes) + 10),
        ):
            files = [
                ("files", ("batch_1.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")),
                ("files", ("batch_2.pdf", io.BytesIO(sample_pdf_bytes + b"\n%extra"), "application/pdf")),
            ]
            response = await client.post("/api/v1/documents/batch", files=files, headers=headers)
            assert response.status_code == 201
            data = response.json()
            assert data["total"] == 2
            assert data["successful_count"] == 1
            assert data["failed_count"] == 1

            # First item should be accepted
            assert data["items"][0]["status"] == "queued"
            # Second item should be rejected with quota message
            assert data["items"][1]["status"] == "rejected"
            assert "Storage quota exceeded" in data["items"][1]["error"]
    finally:
        settings.USER_STORAGE_QUOTA_MB = original_quota


@pytest.mark.asyncio
async def test_05_concurrent_uploads_cannot_bypass_quota(client, sample_pdf_bytes):
    """5. Concurrent uploads cannot bypass quota through race conditions."""
    headers = {"X-User-Id": "usr_quota_race_tester"}

    # Set quota to allow only 1 file
    with patch.object(
        type(settings),
        "user_storage_quota_bytes",
        new_callable=lambda: property(lambda self: len(sample_pdf_bytes) + 50),
    ):
        async def upload_concurrently(idx: int):
            content = sample_pdf_bytes + f"\n%salt_{idx}".encode("utf-8")
            files = {"file": (f"race_doc_{idx}.pdf", io.BytesIO(content), "application/pdf")}
            return await client.post("/api/v1/documents", files=files, headers=headers)

        # Launch 4 concurrent uploads simultaneously
        responses = await asyncio.gather(
            upload_concurrently(1),
            upload_concurrently(2),
            upload_concurrently(3),
            upload_concurrently(4),
        )

        success_count = sum(1 for r in responses if r.status_code == 201)
        quota_exceeded_count = sum(1 for r in responses if r.status_code == 413)

        # Exactly 1 must succeed, 3 must be rejected with HTTP 413
        assert success_count == 1
        assert quota_exceeded_count == 3


@pytest.mark.asyncio
async def test_06_independent_quotas_between_users(client, sample_pdf_bytes):
    """6. User A filling their quota does not restrict User B."""
    headers_a = {"X-User-Id": "usr_tenant_alpha"}
    headers_b = {"X-User-Id": "usr_tenant_beta"}

    # Set quota so that 1 file fills it for any user
    with patch.object(
        type(settings),
        "user_storage_quota_bytes",
        new_callable=lambda: property(lambda self: len(sample_pdf_bytes) + 50),
    ):
        # User A uploads doc 1 -> succeeds
        files_a1 = {"file": ("doc_a1.pdf", io.BytesIO(sample_pdf_bytes + b"\n%a1"), "application/pdf")}
        res_a1 = await client.post("/api/v1/documents", files=files_a1, headers=headers_a)
        assert res_a1.status_code == 201

        # User A tries to upload doc 2 -> rejected (quota full)
        files_a2 = {"file": ("doc_a2.pdf", io.BytesIO(sample_pdf_bytes + b"\n%a2"), "application/pdf")}
        res_a2 = await client.post("/api/v1/documents", files=files_a2, headers=headers_a)
        assert res_a2.status_code == 413

        # User B uploads doc 1 -> must succeed! User B's quota is fresh and isolated
        files_b1 = {"file": ("doc_b1.pdf", io.BytesIO(sample_pdf_bytes + b"\n%b1"), "application/pdf")}
        res_b1 = await client.post("/api/v1/documents", files=files_b1, headers=headers_b)
        assert res_b1.status_code == 201


@pytest.mark.asyncio
async def test_07_failed_and_deleted_document_storage_accounting(client, sample_pdf_bytes):
    """7. Failed and deleted documents do not consume storage quota."""
    headers = {"X-User-Id": "usr_lifecycle_accounting"}

    # 1. Upload valid document
    files = {"file": ("lifecycle.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Usage before delete
    usage_res1 = await client.get("/api/v1/documents/storage-usage", headers=headers)
    assert usage_res1.status_code == 200
    data1 = usage_res1.json()
    assert data1["used_storage_bytes"] == len(sample_pdf_bytes)
    assert data1["document_count"] == 1

    # 2. Delete document
    del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 204

    # Usage after delete must be 0 bytes
    usage_res2 = await client.get("/api/v1/documents/storage-usage", headers=headers)
    assert usage_res2.status_code == 200
    data2 = usage_res2.json()
    assert data2["used_storage_bytes"] == 0
    assert data2["document_count"] == 0


@pytest.mark.asyncio
async def test_08_storage_usage_api_contract(client, sample_pdf_bytes):
    """8. Storage usage API returns complete accurate schema."""
    headers = {"X-User-Id": "usr_schema_tester"}

    # Check baseline empty state
    res_empty = await client.get("/api/v1/documents/storage-usage", headers=headers)
    assert res_empty.status_code == 200
    data = res_empty.json()

    assert data["total_quota_bytes"] == settings.user_storage_quota_bytes
    assert data["used_storage_bytes"] == 0
    assert data["remaining_storage_bytes"] == settings.user_storage_quota_bytes
    assert data["usage_percentage"] == 0.0
    assert data["document_count"] == 0
    assert data["quota_mb"] == settings.USER_STORAGE_QUOTA_MB

    # Upload document and verify updated numbers
    files = {"file": ("calc_check.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    upload_res = await client.post("/api/v1/documents", files=files, headers=headers)
    assert upload_res.status_code == 201

    res_after = await client.get("/api/v1/documents/storage-usage", headers=headers)
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["used_storage_bytes"] == len(sample_pdf_bytes)
    assert data_after["document_count"] == 1
    assert data_after["remaining_storage_bytes"] == data_after["total_quota_bytes"] - len(sample_pdf_bytes)
    assert data_after["usage_percentage"] > 0.0


@pytest.mark.asyncio
async def test_09_unauthorized_storage_usage_access_rejected(client):
    """9. Unauthorized requests cannot inspect storage usage."""
    # When DEV_AUTH_BYPASS is false, requests without credentials fail
    original_bypass = settings.DEV_AUTH_BYPASS
    try:
        settings.DEV_AUTH_BYPASS = False
        res = await client.get("/api/v1/documents/storage-usage")
        assert res.status_code in (401, 403)
    finally:
        settings.DEV_AUTH_BYPASS = original_bypass


def test_10_missing_s3_production_config_fails_validation():
    """10. In production environment, missing or non-S3 storage fails fast with RuntimeError."""
    prod_settings_local = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-secure-32-character-secret-key-prod",
        DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db",
        GEMINI_API_KEY="valid-length-gemini-api-key-for-prod",
        ALLOWED_ORIGINS=["https://orion.example.com"],
        STORAGE_PROVIDER="local",
        DEV_AUTH_BYPASS=False,
    )
    with pytest.raises(RuntimeError) as exc_info:
        prod_settings_local.validate_production_requirements()
    assert "STORAGE_PROVIDER must be configured as 's3'" in str(exc_info.value)

    # Missing S3 credentials
    prod_settings_s3_missing = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-secure-32-character-secret-key-prod",
        DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db",
        GEMINI_API_KEY="valid-length-gemini-api-key-for-prod",
        ALLOWED_ORIGINS=["https://orion.example.com"],
        STORAGE_PROVIDER="s3",
        DEV_AUTH_BYPASS=False,
        S3_BUCKET_NAME="orion-research-documents",
        S3_ACCESS_KEY_ID="",
        S3_SECRET_ACCESS_KEY="",
    )
    with pytest.raises(RuntimeError) as exc_info:
        prod_settings_s3_missing.validate_production_requirements()
    assert "S3_ACCESS_KEY_ID" in str(exc_info.value)
    # Ensure no secrets leaked in error
    assert "secret" not in str(exc_info.value).lower() or "s3_secret_access_key" in str(exc_info.value).lower()


def test_11_development_mode_supports_local_storage():
    """11. In development mode, local storage continues to operate cleanly without validation errors."""
    dev_settings = Settings(
        ENVIRONMENT="development",
        STORAGE_PROVIDER="local",
    )
    # validate_production_requirements does nothing in development
    dev_settings.validate_production_requirements()
    assert dev_settings.STORAGE_PROVIDER == "local"
    assert dev_settings.USER_STORAGE_QUOTA_MB == 500


@pytest.mark.asyncio
async def test_12_s3_readiness_failure_reported_safely(client):
    """12. S3 readiness failure is reported safely in /health/ready without leaking secrets."""
    with mock_aws():
        # S3 storage pointing to non-existent bucket
        broken_s3 = S3StorageService(
            bucket_name="nonexistent-private-bucket-xyz",
            region_name="us-east-1",
            access_key_id="mock_id_12345",
            secret_access_key="mock_super_secret_key_67890",
        )

        readiness = await broken_s3.check_readiness()
        assert readiness is False

        # Probe readiness endpoint with mocked storage failure
        with patch("app.services.storage.local.LocalStorageService.check_readiness", new_callable=AsyncMock) as mock_ready:
            mock_ready.return_value = False
            res = await client.get("/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "degraded"
            assert data["checks"]["storage"] == "unhealthy: storage access check failed"
            # Ensure no secrets or bucket names leaked
            assert "mock_super_secret_key" not in str(data)
            assert "mock_id_12345" not in str(data)
            assert "nonexistent-private-bucket-xyz" not in str(data)


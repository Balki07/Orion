"""Tests for StorageBackend abstraction (LocalStorage and S3Storage via moto)."""

import os
from pathlib import Path
import pytest
import boto3
from moto import mock_aws

from app.core.errors import IngestionError
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService
from app.services.storage.cleanup import cleanup_orphaned_storage, cleanup_user_storage


@pytest.mark.asyncio
async def test_local_storage_lifecycle(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    # 1. Save file
    key = "usr_123/doc_abc/paper.pdf"
    content = b"%PDF-1.4 test document content"
    saved_key = await storage.save(key, content)
    assert saved_key == key

    # 2. Exists
    assert await storage.exists(key) is True
    assert await storage.exists("usr_123/nonexistent.pdf") is False

    # 3. Open
    read_back = await storage.open(key)
    assert read_back == content

    # 4. Save render thumbnail
    render_key = "usr_123/doc_abc/renders/page_1_dpi150.png"
    img_bytes = b"\x89PNG\r\n\x1a\nfakeimage"
    await storage.save(render_key, img_bytes, content_type="image/png")
    assert await storage.exists(render_key) is True

    # 5. Delete single file
    assert await storage.delete(render_key) is True
    assert await storage.exists(render_key) is False

    # 6. Delete prefix
    # Save another render
    await storage.save(render_key, img_bytes, content_type="image/png")
    deleted_count = await storage.delete_prefix("usr_123/doc_abc")
    assert deleted_count >= 2
    assert await storage.exists(key) is False
    assert await storage.exists(render_key) is False


@pytest.mark.asyncio
async def test_local_storage_path_traversal_rejection(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    with pytest.raises(IngestionError) as exc_info:
        await storage.save("../../../etc/passwd", b"malicious")
    assert "traversal" in str(exc_info.value).lower()

    with pytest.raises(IngestionError) as exc_info:
        await storage.open("../../secret.txt")
    assert "traversal" in str(exc_info.value).lower()

    with pytest.raises(IngestionError) as exc_info:
        await storage.delete_prefix("../")
    assert "traversal" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_s3_storage_lifecycle_with_moto():
    with mock_aws():
        # Setup mock S3 bucket
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-orion-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        storage = S3StorageService(
            bucket_name=bucket_name,
            region_name="us-east-1",
            access_key_id="mock_key",
            secret_access_key="mock_secret",
        )

        # 1. Save file
        key = "usr_pilot_1/doc_quantum_1/quantum.pdf"
        content = b"%PDF-1.4 Mock S3 Quantum PDF content"
        saved_key = await storage.save(key, content)
        assert saved_key == key

        # 2. Exists
        assert await storage.exists(key) is True
        assert await storage.exists("usr_pilot_1/nonexistent.pdf") is False

        # 3. Open
        read_back = await storage.open(key)
        assert read_back == content

        # 4. Save page renders
        render_1 = "usr_pilot_1/doc_quantum_1/renders/page_1.png"
        render_2 = "usr_pilot_1/doc_quantum_1/renders/page_2.png"
        await storage.save(render_1, b"png1", content_type="image/png")
        await storage.save(render_2, b"png2", content_type="image/png")
        assert await storage.exists(render_1) is True
        assert await storage.exists(render_2) is True

        # 5. Delete prefix (doc_quantum_1)
        deleted_count = await storage.delete_prefix("usr_pilot_1/doc_quantum_1")
        assert deleted_count == 3
        assert await storage.exists(key) is False
        assert await storage.exists(render_1) is False
        assert await storage.exists(render_2) is False

        # 6. User-level cleanup
        await storage.save("usr_pilot_1/doc_2/paper2.pdf", b"pdf2")
        await storage.save("usr_pilot_1/doc_3/paper3.pdf", b"pdf3")
        purged = await cleanup_user_storage("usr_pilot_1", storage)
        assert purged == 2
        assert await storage.exists("usr_pilot_1/doc_2/paper2.pdf") is False


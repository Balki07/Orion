"""Two-User Multi-Tenant Isolation Tests across LocalStorage and S3Storage (moto).

Validates tenant isolation, cross-tenant 403 rejections, and storage prefix cleanups
against an isolated test database without touching live production databases.
"""

import os
import uuid
import pytest
import pymupdf
import boto3
from moto import mock_aws
from httpx import ASGITransport, AsyncClient
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import Settings
from app.db.base import Base
from app.main import app
from app.api.deps import get_db, get_storage_service
from app.models.user import User
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService
from app.services.ingestion.worker import get_ingestion_worker
from app.security.service import auth_rate_limiter


def create_minimal_pdf(content_text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), content_text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_two_user_isolation_local_storage(tmp_path):
    """Test 2-user tenant isolation end-to-end using LocalStorage."""
    auth_rate_limiter._attempts.clear()
    test_db_url = f"sqlite+aiosqlite:///{tmp_path}/test_isolation.db"
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

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            uid_a = uuid.uuid4().hex[:8]
            uid_b = uuid.uuid4().hex[:8]

            # 1. Register User A
            reg_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"isolated_user_a_{uid_a}@test.orion.ai",
                    "password": "ValidPassword123!#",
                    "display_name": "Test User A",
                },
            )
            assert reg_a.status_code == 201, reg_a.text
            user_a_id = reg_a.json()["user"]["id"]
            token_a = reg_a.json()["access_token"]
            csrf_a = reg_a.json()["csrf_token"]
            headers_a = {"Authorization": f"Bearer {token_a}", "X-CSRF-Token": csrf_a}

            # 2. Register User B
            reg_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"isolated_user_b_{uid_b}@test.orion.ai",
                    "password": "ValidPassword123!#",
                    "display_name": "Test User B",
                },
            )
            assert reg_b.status_code == 201, reg_b.text
            user_b_id = reg_b.json()["user"]["id"]
            token_b = reg_b.json()["access_token"]
            csrf_b = reg_b.json()["csrf_token"]
            headers_b = {"Authorization": f"Bearer {token_b}", "X-CSRF-Token": csrf_b}

            # Activate researchers to allow research workspace operations
            async with TestSessionLocal() as db_sess:
                await db_sess.execute(
                    sa.update(User)
                    .where(User.id.in_([user_a_id, user_b_id]))
                    .values(access_status="active")
                )
                await db_sess.commit()

            # 3. User A uploads PDF A
            pdf_a_bytes = create_minimal_pdf("Quantum entanglement enables quantum teleportation protocols.")
            up_a = await client.post(
                "/api/v1/documents",
                files={"file": ("quantum_a.pdf", pdf_a_bytes, "application/pdf")},
                headers=headers_a,
            )
            assert up_a.status_code == 201, up_a.text
            doc_a_id = up_a.json()["id"]

            # 4. User B uploads PDF B
            pdf_b_bytes = create_minimal_pdf("Photosynthesis converts carbon dioxide into glucose molecules.")
            up_b = await client.post(
                "/api/v1/documents",
                files={"file": ("biology_b.pdf", pdf_b_bytes, "application/pdf")},
                headers=headers_b,
            )
            assert up_b.status_code == 201, up_b.text
            doc_b_id = up_b.json()["id"]

            # 5. User B cross-tenant document access rejections
            cross_get = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert cross_get.status_code == 403, "User B accessed User A metadata!"

            cross_file = await client.get(f"/api/v1/documents/{doc_a_id}/file", headers=headers_b)
            assert cross_file.status_code == 403, "User B accessed User A raw PDF file!"

            cross_render = await client.get(f"/api/v1/documents/{doc_a_id}/pages/1/render", headers=headers_b)
            assert cross_render.status_code == 403, "User B accessed User A page render!"

            cross_del = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert cross_del.status_code == 403, "User B deleted User A document!"

            # 6. Verify User A storage files exist
            assert await local_storage.exists(f"{user_a_id}/{doc_a_id}/quantum_a.pdf") is True

            # 7. User A deletes their own document
            del_a = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_a)
            assert del_a.status_code == 204

            # Verify storage prefix was cleaned up
            assert await local_storage.exists(f"{user_a_id}/{doc_a_id}/quantum_a.pdf") is False

            # Verify User B's file is 100% intact
            assert await local_storage.exists(f"{user_b_id}/{doc_b_id}/biology_b.pdf") is True

    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_two_user_isolation_s3_storage(tmp_path):
    """Test 2-user tenant isolation end-to-end using S3Storage with moto."""
    auth_rate_limiter._attempts.clear()
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket_name = "orion-test-isolation-bucket"
        s3_client.create_bucket(Bucket=bucket_name)

        s3_storage = S3StorageService(
            bucket_name=bucket_name,
            region_name="us-east-1",
            access_key_id="mock_key",
            secret_access_key="mock_secret",
        )

        test_db_url = f"sqlite+aiosqlite:///{tmp_path}/test_isolation_s3.db"
        test_engine = create_async_engine(test_db_url, connect_args={"check_same_thread": False})
        TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with TestSessionLocal() as session:
                yield session

        def override_get_storage():
            return s3_storage

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_storage_service] = override_get_storage

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                uid_a = uuid.uuid4().hex[:8]
                uid_b = uuid.uuid4().hex[:8]

                # 1. Register User A
                reg_a = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"s3_user_a_{uid_a}@test.orion.ai",
                        "password": "ValidPassword123!#",
                        "display_name": "S3 User A",
                    },
                )
                assert reg_a.status_code == 201
                user_a_id = reg_a.json()["user"]["id"]
                token_a = reg_a.json()["access_token"]
                csrf_a = reg_a.json()["csrf_token"]
                headers_a = {"Authorization": f"Bearer {token_a}", "X-CSRF-Token": csrf_a}

                # 2. Register User B
                reg_b = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"s3_user_b_{uid_b}@test.orion.ai",
                        "password": "ValidPassword123!#",
                        "display_name": "S3 User B",
                    },
                )
                assert reg_b.status_code == 201
                user_b_id = reg_b.json()["user"]["id"]
                token_b = reg_b.json()["access_token"]
                csrf_b = reg_b.json()["csrf_token"]
                headers_b = {"Authorization": f"Bearer {token_b}", "X-CSRF-Token": csrf_b}

                # Activate researchers to allow research workspace operations
                async with TestSessionLocal() as db_sess:
                    await db_sess.execute(
                        sa.update(User)
                        .where(User.id.in_([user_a_id, user_b_id]))
                        .values(access_status="active")
                    )
                    await db_sess.commit()

                # 3. User A uploads PDF A to S3
                pdf_a_bytes = create_minimal_pdf("Superconducting qubits operate at millikelvin temperatures.")
                up_a = await client.post(
                    "/api/v1/documents",
                    files={"file": ("quantum_s3.pdf", pdf_a_bytes, "application/pdf")},
                    headers=headers_a,
                )
                assert up_a.status_code == 201
                doc_a_id = up_a.json()["id"]

                # 4. User B uploads PDF B to S3
                pdf_b_bytes = create_minimal_pdf("Photosynthetic reaction centers absorb photons.")
                up_b = await client.post(
                    "/api/v1/documents",
                    files={"file": ("photosynthesis_s3.pdf", pdf_b_bytes, "application/pdf")},
                    headers=headers_b,
                )
                assert up_b.status_code == 201
                doc_b_id = up_b.json()["id"]

                # 5. Cross-tenant 403 checks in S3
                cross_file = await client.get(f"/api/v1/documents/{doc_a_id}/file", headers=headers_b)
                assert cross_file.status_code == 403

                cross_render = await client.get(f"/api/v1/documents/{doc_a_id}/pages/1/render", headers=headers_b)
                assert cross_render.status_code == 403

                cross_del = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
                assert cross_del.status_code == 403

                # 6. Verify User A S3 object exists
                assert await s3_storage.exists(f"{user_a_id}/{doc_a_id}/quantum_s3.pdf") is True

                # 7. User A deletes their own document
                del_a = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_a)
                assert del_a.status_code == 204

                # Verify S3 prefix was purged
                assert await s3_storage.exists(f"{user_a_id}/{doc_a_id}/quantum_s3.pdf") is False

                # Verify User B's S3 object remains 100% intact
                assert await s3_storage.exists(f"{user_b_id}/{doc_b_id}/photosynthesis_s3.pdf") is True

        finally:
            app.dependency_overrides.clear()
            await test_engine.dispose()

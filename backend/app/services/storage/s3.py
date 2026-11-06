"""S3-compatible Storage Backend (AWS S3 / Cloudflare R2) using boto3."""

import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.errors import IngestionError
from app.core.logging import logger
from app.services.storage.base import StorageService


class S3StorageService(StorageService):
    """StorageBackend implementation for S3-compatible object stores (Cloudflare R2, AWS S3, MinIO)."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
        region_name: str | None = None,
    ):
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self.bucket = bucket_name or settings.S3_BUCKET_NAME or "orion-research-documents"
        self.region_name = region_name or settings.S3_REGION_NAME or "auto"

        # Cloudflare R2 / S3 client configuration
        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region_name,
            "config": Config(
                s3={"addressing_style": "virtual" if not self.endpoint_url else "path"},
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        self.client = boto3.client(**client_kwargs)

    def _normalize_key(self, storage_key: str) -> str:
        clean = storage_key.replace("\\", "/").strip("/")
        if ".." in clean or clean.startswith("/"):
            raise IngestionError("Invalid characters or path traversal attempt in S3 key.", stage="storage")
        return clean

    async def save(self, storage_key: str, content: bytes, content_type: str = "application/pdf") -> str:
        key = self._normalize_key(storage_key)

        def _sync_put():
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            return key

        return await asyncio.to_thread(_sync_put)

    async def open(self, storage_key: str) -> bytes:
        key = self._normalize_key(storage_key)

        def _sync_get():
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                return response["Body"].read()
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                if code in ("NoSuchKey", "404", "NotFound"):
                    raise FileNotFoundError(f"Key '{key}' not found in S3 bucket '{self.bucket}'.") from e
                logger.error(f"S3 get_object error for key '{key}': {e}", exc_info=True)
                raise

        return await asyncio.to_thread(_sync_get)

    async def delete(self, storage_key: str) -> bool:
        key = self._normalize_key(storage_key)

        def _sync_delete():
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError as e:
                logger.warning(f"S3 delete_object failed for key '{key}': {e}")
                return False

        return await asyncio.to_thread(_sync_delete)

    async def delete_prefix(self, prefix: str) -> int:
        """Batch delete all objects with a given key prefix (e.g. {user_id}/{document_id} or {user_id})."""
        clean_prefix = self._normalize_key(prefix)
        if not clean_prefix:
            return 0

        def _sync_delete_prefix():
            paginator = self.client.get_paginator("list_objects_v2")
            deleted_count = 0

            for page in paginator.paginate(Bucket=self.bucket, Prefix=clean_prefix):
                contents = page.get("Contents", [])
                if not contents:
                    continue

                objects_to_delete = [{"Key": obj["Key"]} for obj in contents]
                # S3 delete_objects takes up to 1000 keys
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i : i + 1000]
                    resp = self.client.delete_objects(
                        Bucket=self.bucket,
                        Delete={"Objects": batch, "Quiet": True},
                    )
                    deleted_count += len(batch) - len(resp.get("Errors", []))

            return deleted_count

        return await asyncio.to_thread(_sync_delete_prefix)

    async def exists(self, storage_key: str) -> bool:
        key = self._normalize_key(storage_key)

        def _sync_exists():
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                if code in ("NoSuchKey", "404", "NotFound"):
                    return False
                logger.warning(f"S3 head_object error for key '{key}': {e}")
                return False

        return await asyncio.to_thread(_sync_exists)

    async def check_readiness(self) -> bool:
        """Verify S3 bucket accessibility via head_bucket without leaking secrets."""
        def _sync_ready():
            try:
                self.client.head_bucket(Bucket=self.bucket)
                return True
            except Exception as e:
                logger.error("S3 check_readiness failed: storage bucket unreachable.")
                return False

        return await asyncio.to_thread(_sync_ready)



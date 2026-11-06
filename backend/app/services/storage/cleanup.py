"""Orphaned Storage Cleanup Service."""

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document
from app.models.user import User
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService


async def cleanup_user_storage(user_id: str, storage: StorageService) -> int:
    """Purge all storage objects for a given user prefix."""
    prefix = f"{user_id}/"
    try:
        deleted = await storage.delete_prefix(prefix)
        logger.info(f"Purged {deleted} storage objects for user prefix '{prefix}'")
        return deleted
    except Exception as e:
        logger.warning(f"Error purging user storage for '{prefix}': {e}")
        return 0


async def cleanup_orphaned_storage(db: AsyncSession, storage: StorageService) -> int:
    """Identify and delete storage folders whose document records no longer exist in DB."""
    # 1. Fetch all valid document IDs from database
    result = await db.execute(select(Document.id, Document.owner_id))
    valid_doc_map: dict[str, set[str]] = {}
    for doc_id, owner_id in result.all():
        valid_doc_map.setdefault(owner_id, set()).add(doc_id)

    total_purged = 0

    # 2. Local storage scanning
    if isinstance(storage, LocalStorageService):
        base_dir = storage.base_path
        if not base_dir.exists():
            return 0

        for user_dir in base_dir.iterdir():
            if not user_dir.is_dir():
                continue
            user_id = user_dir.name
            known_docs = valid_doc_map.get(user_id, set())

            for doc_dir in user_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                doc_id = doc_dir.name
                if doc_id not in known_docs:
                    logger.info(f"Detected orphaned local storage directory: {doc_dir}")
                    total_purged += await storage.delete_prefix(f"{user_id}/{doc_id}")

    # 3. S3 storage scanning
    elif isinstance(storage, S3StorageService):
        # List top-level prefixes under bucket
        paginator = storage.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=storage.bucket, Delimiter="/"):
            for prefix_info in page.get("CommonPrefixes", []):
                user_id = prefix_info.get("Prefix", "").strip("/")
                if not user_id:
                    continue
                known_docs = valid_doc_map.get(user_id, set())

                # List sub-prefixes (doc_ids) under this user
                sub_page = storage.client.list_objects_v2(
                    Bucket=storage.bucket,
                    Prefix=f"{user_id}/",
                    Delimiter="/",
                )
                for sub_prefix in sub_page.get("CommonPrefixes", []):
                    doc_prefix = sub_prefix.get("Prefix", "").strip("/")
                    # doc_prefix is "user_id/doc_id"
                    parts = doc_prefix.split("/")
                    if len(parts) >= 2:
                        doc_id = parts[1]
                        if doc_id not in known_docs:
                            logger.info(f"Detected orphaned S3 storage prefix: {doc_prefix}")
                            total_purged += await storage.delete_prefix(doc_prefix)

    return total_purged


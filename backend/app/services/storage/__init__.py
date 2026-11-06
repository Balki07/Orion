"""Storage Service Factory supporting Local and S3-compatible cloud storage."""

from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageBackend, StorageService
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService
from app.services.storage.supabase import SupabaseStorageService


@lru_cache
def get_storage_service() -> StorageService:
    """Return configured StorageBackend singleton."""
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "s3":
        return S3StorageService()
    if provider == "supabase" and settings.SUPABASE_URL:
        return SupabaseStorageService()
    return LocalStorageService()


__all__ = [
    "LocalStorageService",
    "S3StorageService",
    "StorageBackend",
    "StorageService",
    "SupabaseStorageService",
    "get_storage_service",
]

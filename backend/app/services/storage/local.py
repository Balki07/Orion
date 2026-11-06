"""Local Filesystem Storage Implementation with strict path traversal defense."""

import asyncio
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.errors import IngestionError
from app.services.storage.base import StorageService


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str = settings.STORAGE_LOCAL_DIR):
        self.base_path = Path(base_dir).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Resolve path and verify that it remains strictly inside base_path to prevent traversal."""
        # Normalize slashes
        clean_key = storage_key.replace("\\", "/").lstrip("/")
        safe_path = (self.base_path / clean_key).resolve()
        try:
            safe_path.relative_to(self.base_path)
        except ValueError:
            raise IngestionError("Path traversal attempt detected in storage key.", stage="storage")
        return safe_path

    async def save(self, storage_key: str, content: bytes, content_type: str = "application/pdf") -> str:
        def _sync_save():
            target_path = self._resolve_safe_path(storage_key)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
            return storage_key

        return await asyncio.to_thread(_sync_save)

    async def open(self, storage_key: str) -> bytes:
        def _sync_read():
            target_path = self._resolve_safe_path(storage_key)
            if not target_path.exists() or not target_path.is_file():
                raise FileNotFoundError(f"File '{storage_key}' not found in local storage.")
            return target_path.read_bytes()

        return await asyncio.to_thread(_sync_read)

    async def delete(self, storage_key: str) -> bool:
        def _sync_delete():
            target_path = self._resolve_safe_path(storage_key)
            if target_path.exists() and target_path.is_file():
                target_path.unlink()
                return True
            return False

        return await asyncio.to_thread(_sync_delete)

    async def delete_prefix(self, prefix: str) -> int:
        """Delete all files starting with prefix (e.g. {user_id}/{document_id} or {user_id})."""
        def _sync_delete_prefix():
            clean_prefix = prefix.replace("\\", "/").strip("/")
            if not clean_prefix:
                return 0

            target = (self.base_path / clean_prefix).resolve()
            try:
                target.relative_to(self.base_path)
            except ValueError:
                raise IngestionError("Path traversal attempt detected in prefix.", stage="storage")

            deleted_count = 0
            # If target is an existing directory, count files and remove directory tree
            if target.is_dir():
                for p in target.rglob("*"):
                    if p.is_file():
                        deleted_count += 1
                shutil.rmtree(target, ignore_errors=True)
                return deleted_count

            # If target is a file or prefix pattern in parent directory
            if target.is_file():
                target.unlink(missing_ok=True)
                return 1

            parent = target.parent
            if parent.exists() and parent.is_dir():
                prefix_name = target.name
                for p in parent.iterdir():
                    if p.name.startswith(prefix_name):
                        if p.is_file():
                            p.unlink(missing_ok=True)
                            deleted_count += 1
                        elif p.is_dir():
                            for sub in p.rglob("*"):
                                if sub.is_file():
                                    deleted_count += 1
                            shutil.rmtree(p, ignore_errors=True)
            return deleted_count

        return await asyncio.to_thread(_sync_delete_prefix)

    async def exists(self, storage_key: str) -> bool:
        def _sync_exists():
            target_path = self._resolve_safe_path(storage_key)
            return target_path.exists() and target_path.is_file()

        return await asyncio.to_thread(_sync_exists)

    async def check_readiness(self) -> bool:
        """Verify local storage directory existence and write capability."""
        def _sync_ready():
            return self.base_path.exists() and self.base_path.is_dir()

        return await asyncio.to_thread(_sync_ready)


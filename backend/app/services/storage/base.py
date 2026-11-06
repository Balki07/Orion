"""Storage Service Abstract Base Class defining the StorageBackend interface."""

from abc import ABC, abstractmethod


class StorageService(ABC):
    """StorageBackend interface supporting Local and S3-compatible cloud storage."""

    @abstractmethod
    async def save(self, storage_key: str, content: bytes, content_type: str = "application/pdf") -> str:
        """Saves file bytes to destination storage key and returns storage key."""

    @abstractmethod
    async def open(self, storage_key: str) -> bytes:
        """Reads and returns file bytes from storage key."""

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        """Deletes file at storage key. Returns True if deleted or already gone."""

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int:
        """Deletes all objects whose keys start with prefix. Returns number of deleted items."""

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Returns True if file exists at storage key."""

    @abstractmethod
    async def check_readiness(self) -> bool:
        """Verifies storage backend readiness without disclosing credentials."""

    # Backward compatibility aliases for existing codebase
    async def save_file(self, content: bytes, storage_key: str, content_type: str = "application/pdf") -> str:
        return await self.save(storage_key, content, content_type)

    async def read_file(self, storage_key: str) -> bytes:
        return await self.open(storage_key)

    async def delete_file(self, storage_key: str) -> bool:
        return await self.delete(storage_key)

    async def file_exists(self, storage_key: str) -> bool:
        return await self.exists(storage_key)


StorageBackend = StorageService

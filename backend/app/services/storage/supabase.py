"""Supabase Storage Service Implementation."""

import httpx

from app.core.config import settings
from app.services.storage.base import StorageService


class SupabaseStorageService(StorageService):
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL or ""
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY or ""
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    async def save_file(self, content: bytes, storage_key: str) -> str:
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{storage_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                content=content,
                headers={**self.headers, "Content-Type": "application/pdf"},
                timeout=30.0,
            )
            resp.raise_for_status()
        return storage_key

    async def read_file(self, storage_key: str) -> bytes:
        url = f"{self.supabase_url}/storage/v1/object/authenticated/{self.bucket}/{storage_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, timeout=30.0)
            resp.raise_for_status()
            return resp.content

    async def delete_file(self, storage_key: str) -> bool:
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{storage_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self.headers, timeout=30.0)
            return resp.status_code in (200, 204)

    async def file_exists(self, storage_key: str) -> bool:
        try:
            await self.read_file(storage_key)
            return True
        except Exception:
            return False

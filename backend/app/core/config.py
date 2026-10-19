"""ORION application configuration and environment settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Identity & Mode
    APP_NAME: str = "ORION"
    APP_VERSION: str = "0.1.0"
    ORION_ENV: Literal["development", "staging", "production"] = "development"
    ORION_SECRET_KEY: str = Field(
        default="orion-dev-insecure-secret-key-32-chars-minimum-change-in-prod",
        description="Session and token signing key",
    )
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server & Networking
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database & pgvector
    # Supports postgresql+asyncpg:// for production and sqlite+aiosqlite:// for zero-dependency tests
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./storage/orion_dev.db",
        description="Async database connection string",
    )
    DATABASE_URL_SYNC: str | None = None

    # Authentication & Supabase
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None
    DEV_AUTH_BYPASS: bool = True

    # Storage Provider
    STORAGE_PROVIDER: Literal["local", "supabase"] = "local"
    STORAGE_LOCAL_DIR: str = "./storage/uploads"
    SUPABASE_STORAGE_BUCKET: str = "research-documents"
    MAX_UPLOAD_SIZE_MB: int = 32
    MAX_PDF_PAGES: int = 200

    # LLM (Google Gemini via google-genai)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_OUTPUT_TOKENS: int = 2048

    # Local Embedding Model
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "cpu"

    # Ingestion & Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80

    # Retrieval Engine
    RETRIEVAL_TOP_K: int = 8
    HYBRID_FUSION_ALPHA: float = 0.6  # Weight between dense and lexical scores in RRF
    RERANKER_ENABLED: bool = False
    RERANKER_MODEL: str = "BAAI/bge-reranker-small"

    # Observability
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str | None = "https://cloud.langfuse.com"

    @field_validator("DEV_AUTH_BYPASS")
    @classmethod
    def enforce_production_security(cls, v: bool, info) -> bool:
        """Never allow DEV_AUTH_BYPASS in production environment."""
        env = info.data.get("ORION_ENV", "development")
        if env == "production" and v:
            raise ValueError("DEV_AUTH_BYPASS cannot be True in production environment.")
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()


# Singleton instance
settings = Settings()

# Ensure local storage directory exists
if settings.STORAGE_PROVIDER == "local":
    Path(settings.STORAGE_LOCAL_DIR).mkdir(parents=True, exist_ok=True)

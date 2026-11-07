"""ORION application configuration and environment settings."""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Identity & Mode
    APP_NAME: str = "ORION"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] | None = None
    ORION_ENV: Literal["development", "staging", "production", "test"] = "development"
    SECRET_KEY: str | None = None
    ORION_SECRET_KEY: str = Field(
        default="orion-dev-insecure-secret-key-32-chars-minimum-change-in-prod",
        description="Session and token signing key",
    )
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server & Networking
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    PORT: int | None = None
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] | str = [
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
    DEV_AUTH_BYPASS: bool = False
    ADMIN_EMAILS: list[str] | str = [
        "orionadmin@gmail.com",
        "admin@orion-assistant.ai",
        "admin@orion.ai",
    ]
    ADMIN_USER_IDS: list[str] | str = ["user_admin_001"]

    # Authentication & Session Security
    SESSION_COOKIE_NAME: str = "orion_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    CSRF_COOKIE_NAME: str = "orion_csrf"
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 60
    RATE_LIMIT_REGISTER_MAX_ATTEMPTS: int = 3
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = 60

    # Storage Provider
    STORAGE_PROVIDER: Literal["local", "s3", "supabase"] = "local"
    STORAGE_LOCAL_DIR: str = "./storage/uploads"
    SUPABASE_STORAGE_BUCKET: str = "research-documents"

    # S3 / Cloudflare R2 Configuration
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str = "orion-research-documents"
    S3_REGION_NAME: str = "auto"

    # Ingestion & Upload Caps
    MAX_UPLOAD_SIZE_MB: int = 32
    MAX_PDF_PAGES: int = 200
    MAX_BATCH_FILES: int = 10
    MAX_BATCH_SIZE_MB: int = 128
    USER_STORAGE_QUOTA_MB: int = 500
    USER_DOCUMENT_LIMIT: int = 50
    INGESTION_WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    INGESTION_MAX_RETRIES: int = 3
    INGESTION_STUCK_TIMEOUT_SECONDS: int = 180
    INGESTION_WATCHDOG_INTERVAL_SECONDS: float = 15.0

    # LLM (Google Gemini via google-genai)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_OUTPUT_TOKENS: int = 2048
    GEMINI_REQUESTS_PER_MINUTE: int = 15
    GEMINI_MAX_RETRIES: int = 1
    GEMINI_TIMEOUT_SECONDS: float = 12.0
    GEMINI_RETRY_BACKOFF_BASE_SECONDS: float = 0.5
    GEMINI_RETRY_BACKOFF_MAX_SECONDS: float = 2.0
    GEMINI_MAX_TOTAL_RETRY_WAIT_SECONDS: float = 5.0
    GEMINI_FALLBACK_MODEL: str | None = None

    # Local Embedding Model (FastEmbed ONNX Runtime by default; SentenceTransformers for comparison)
    EMBEDDING_PROVIDER: str = "fastembed"  # "fastembed" | "sentence_transformers"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_DEVICE: str = "cpu"
    ONNX_NUM_THREADS: int = 1
    FASTEMBED_CACHE_DIR: str | None = None

    # Ingestion & Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 80

    # Retrieval Engine
    RETRIEVAL_TOP_K: int = 8
    HYBRID_FUSION_ALPHA: float = 0.6  # Weight between dense and lexical scores in RRF
    RERANKER_ENABLED: bool = False
    RERANKER_MODEL: str = "BAAI/bge-reranker-small"
    HNSW_EF_SEARCH: int = 40

    # Observability & Diagnostics
    RAG_DIAGNOSTICS_ENABLED: bool = True
    RAG_DIAGNOSTICS_EXCERPTS: bool = False
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str | None = "https://cloud.langfuse.com"

    # Evaluation & Ablation Feature Flags
    FLAG_MODIFIER_FRAGMENT_SANITIZATION: bool = False
    FLAG_ORIGINAL_QUERY_EXTRA_PASS: bool = False
    FLAG_FULL_CANDIDATE_POOL: bool = True
    FLAG_MULTI_LIST_RRF: bool = False
    FLAG_SOURCE_DIVERSITY: bool = False
    FLAG_LIBRARY_LEVEL_ENTITY_CHECK: bool = True

    # Step 1 Quality Improvement Flags
    FLAG_CROSS_05_EXCERPT_SELECTION: bool = False
    FLAG_CROSS_01_FIRST_PAGE_ABSTRACT: bool = True
    FLAG_CROSS_02_DISCLOSURE: bool = True
    FLAG_CITATION_PAGE_ACCURACY: bool = False
    FLAG_DUPLICATE_CHUNK_COLLAPSE: bool = False
    FLAG_FACT_AWARE_CITATION_SELECTION: bool = True

    # Public Demo Mode & Cost Control Guardrails
    ORION_ENABLE_PUBLIC_DEMO: bool = True
    DEMO_DAILY_GEMINI_BUDGET: int = 200
    DEMO_IP_RATE_LIMIT_PER_MINUTE: int = 5
    DEMO_VISITOR_DAILY_QUERY_LIMIT: int = 20
    DEMO_MAX_QUERY_LENGTH: int = 250
    DEMO_QUERY_TIMEOUT_SECONDS: float = 10.0
    DEMO_STORAGE_DIR: str = "./storage/demo_corpus"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        """Support comma-separated or JSON list strings for ALLOWED_ORIGINS."""
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [orig.strip() for orig in v_str.split(",") if orig.strip()]
        return v or []

    @field_validator("ADMIN_EMAILS", "ADMIN_USER_IDS", mode="after")
    @classmethod
    def parse_comma_separated_admin_lists(cls, v: Any) -> list[str]:
        """Support comma-separated strings or lists for admin environment variables."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return []

    @model_validator(mode="after")
    def sync_aliases_and_env(self) -> "Settings":
        """Synchronize alias fields across configuration."""
        if self.ENVIRONMENT and not self.ORION_ENV:
            self.ORION_ENV = self.ENVIRONMENT
        elif self.ENVIRONMENT:
            self.ORION_ENV = self.ENVIRONMENT

        if self.SECRET_KEY:
            self.ORION_SECRET_KEY = self.SECRET_KEY
        elif self.ORION_SECRET_KEY:
            self.SECRET_KEY = self.ORION_SECRET_KEY

        # Dynamic port resolution (e.g. Render, Cloud Run, Heroku)
        if self.PORT is not None:
            self.BACKEND_PORT = self.PORT

        # In production, secure cookie is mandatory
        if self.effective_env == "production":
            self.SESSION_COOKIE_SECURE = True
            if self.DEV_AUTH_BYPASS:
                raise ValueError("DEV_AUTH_BYPASS cannot be True in production environment.")

        return self

    @property
    def effective_env(self) -> str:
        return self.ENVIRONMENT or self.ORION_ENV

    @property
    def effective_secret_key(self) -> str:
        return self.SECRET_KEY or self.ORION_SECRET_KEY

    @property
    def effective_port(self) -> int:
        return self.PORT or self.BACKEND_PORT

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def max_batch_size_bytes(self) -> int:
        return self.MAX_BATCH_SIZE_MB * 1024 * 1024

    @property
    def user_storage_quota_bytes(self) -> int:
        return self.USER_STORAGE_QUOTA_MB * 1024 * 1024

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    def validate_production_requirements(self) -> None:
        """Fail fast on startup if production requirements are missing or default."""
        if self.effective_env != "production":
            return

        reasons = []
        # 1. SECRET_KEY
        key = self.effective_secret_key
        if not key or key == "orion-dev-insecure-secret-key-32-chars-minimum-change-in-prod" or len(key) < 32:
            reasons.append("SECRET_KEY must be a cryptographically secure string with at least 32 characters in production.")

        # 2. DATABASE_URL
        if not self.DATABASE_URL or "sqlite" in self.DATABASE_URL.lower():
            reasons.append("DATABASE_URL must target a production PostgreSQL service with pgvector, not SQLite.")

        # 3. GEMINI_API_KEY
        if not self.GEMINI_API_KEY or len(self.GEMINI_API_KEY.strip()) < 10 or "your-gemini" in self.GEMINI_API_KEY.lower():
            reasons.append("GEMINI_API_KEY must be a valid Google AI Studio API key in production.")

        # 4. ALLOWED_ORIGINS
        origins = self.ALLOWED_ORIGINS if isinstance(self.ALLOWED_ORIGINS, list) else [self.ALLOWED_ORIGINS]
        is_all_local = all("localhost" in str(o) or "127.0.0.1" in str(o) for o in origins)
        if not origins or is_all_local:
            reasons.append("ALLOWED_ORIGINS must include at least one production domain (not only localhost/127.0.0.1).")

        # 5. Production Storage Provider must be S3 with non-empty credentials
        if self.STORAGE_PROVIDER != "s3":
            reasons.append("STORAGE_PROVIDER must be configured as 's3' in production environments.")
        else:
            if not self.S3_ACCESS_KEY_ID or not self.S3_SECRET_ACCESS_KEY or not self.S3_BUCKET_NAME:
                reasons.append("S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, and S3_BUCKET_NAME are required when STORAGE_PROVIDER=s3.")

        if reasons:
            error_msg = "FATAL: Production configuration validation failed:\n" + "\n".join(f" - {r}" for r in reasons)
            raise RuntimeError(error_msg)


# Singleton instance
settings = Settings()

# Ensure local storage directory exists
if settings.STORAGE_PROVIDER == "local":
    Path(settings.STORAGE_LOCAL_DIR).mkdir(parents=True, exist_ok=True)

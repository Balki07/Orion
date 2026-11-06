# ORION — Production Environment Variables Checklist

This document details all required and optional environment variables across the ORION application stack (FastAPI Backend on Render and React Frontend on Vercel).

> [!CAUTION]
> Never commit actual secret keys, database passwords, or API credentials to version control. This document provides variable names, formats, and safe examples only.

---

## 1. Backend Web Service (Render Environment)

### A. Core Application & Server Runtime

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | string | `development` | **Mandatory:** `production` | Active runtime environment. Enforces strict production validation on boot. |
| `ORION_ENV` | string | `development` | **Mandatory:** `production` | Alias for `ENVIRONMENT`. Synchronized automatically by settings validator. |
| `BACKEND_HOST` | string | `0.0.0.0` | `0.0.0.0` | Network binding interface. Must bind to all interfaces in containers. |
| `PORT` | int | None | Injected by PaaS | Dynamic port assigned by Render runtime (e.g. `10000` or `8000`). |
| `BACKEND_PORT` | int | `8000` | `8000` or `$PORT` | Fallback port if `$PORT` is not defined. |
| `DEBUG` | bool | `false` | **Must be `false`** | Debug mode toggle. Suppresses verbose internal tracebacks in production. |
| `LOG_LEVEL` | string | `INFO` | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

### B. Cryptographic Security & Authentication

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `SECRET_KEY` | string | Dev placeholder | **Mandatory (>= 32 chars)** | Cryptographically secure random string used to sign session JWTs. Must not be default dev key. |
| `ORION_SECRET_KEY` | string | Dev placeholder | **Mandatory** | Alias for `SECRET_KEY`. Kept in sync by model validator. |
| `DEV_AUTH_BYPASS` | bool | `false` | **Mandatory: `false`** | Fails fast with `ValueError` on boot if set to `true` when `ENVIRONMENT=production`. |
| `SESSION_COOKIE_NAME` | string | `orion_session` | `orion_session` | Name of the HttpOnly session cookie storing user JWT. |
| `CSRF_COOKIE_NAME` | string | `orion_csrf` | `orion_csrf` | Name of the client-readable CSRF token cookie. |
| `SESSION_COOKIE_SECURE` | bool | `false` | **Enforced `true` in prod** | When `ENVIRONMENT=production`, automatically coerced to `true` (HTTPS only). |
| `SESSION_COOKIE_SAMESITE` | string | `lax` | `lax` (or `none` for cross-site) | SameSite cookie attribute. `lax` when using Vercel API rewrite proxy. |
| `SESSION_EXPIRE_MINUTES` | int | `10080` (7 days) | `10080` | Session lifetime before mandatory re-authentication. |

### C. CORS & Networking

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `ALLOWED_ORIGINS` | list / string | Localhost array | **Mandatory** | Comma-separated list or JSON array of authorized origins (e.g. `https://app.orion-assistant.ai,https://orion-staging.vercel.app`). Cannot contain only localhost in production. |
| `FRONTEND_ORIGIN` | string | `http://localhost:5173` | Production URL | Primary frontend origin for reference headers. |

### D. Aiven PostgreSQL Database & pgvector

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | string | SQLite dev db | **Mandatory** | Asyncpg connection URL: `postgresql+asyncpg://<username>:<password>@<aiven-host>:<port>/defaultdb?ssl=require`. Target must be PostgreSQL, not SQLite. |
| `HNSW_EF_SEARCH` | int | `40` | `40` | HNSW search depth parameter applied per-session (`SET hnsw.ef_search = 40;`). |

### E. Cloudflare R2 / S3-Compatible Object Storage

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `STORAGE_PROVIDER` | string | `local` | **Mandatory: `s3`** | Storage engine. When `ENVIRONMENT=production`, startup validator rejects `local` storage. |
| `S3_ENDPOINT_URL` | string | None | **Mandatory for R2** | Cloudflare R2 API endpoint: `https://<account_id>.r2.cloudflarestorage.com`. |
| `S3_ACCESS_KEY_ID` | string | None | **Mandatory** | Cloudflare R2 / S3 access key ID (minimum 16 characters). |
| `S3_SECRET_ACCESS_KEY`| string | None | **Mandatory** | Cloudflare R2 / S3 secret access key. |
| `S3_BUCKET_NAME` | string | `orion-research-documents` | **Mandatory** | Bucket name holding user PDFs and rendered page thumbnails. |
| `S3_REGION_NAME` | string | `auto` | `auto` | Bucket region (use `auto` for Cloudflare R2). |
| `USER_STORAGE_QUOTA_MB`| int | `500` | `500` | Cumulative storage quota per user in megabytes. |

### F. Google Gemini AI API

| Variable Name | Type | Default | Production Requirement | Description & Format |
| :--- | :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | string | None | **Mandatory** | Valid Google AI Studio API key (length >= 10, cannot contain placeholder text). |
| `GEMINI_MODEL` | string | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | Active generative model identifier. |
| `GEMINI_TEMPERATURE` | float | `0.1` | `0.1` | Sampling temperature for factual research synthesis. |
| `GEMINI_MAX_OUTPUT_TOKENS` | int | `2048` | `2048` | Maximum tokens per response. |
| `GEMINI_REQUESTS_PER_MINUTE` | int | `15` | `15` | Provider rate limit benchmark. |

### G. Ingestion & Chunking Safeguards

| Variable Name | Type | Default | Description & Safeguard |
| :--- | :--- | :--- | :--- |
| `MAX_UPLOAD_SIZE_MB` | int | `32` | Maximum allowable size per individual research PDF (32 MB). |
| `MAX_PDF_PAGES` | int | `200` | Maximum page count per document (rejects excessive files). |
| `MAX_BATCH_FILES` | int | `10` | Maximum documents submitted in a single batch request. |
| `MAX_BATCH_SIZE_MB` | int | `128` | Maximum aggregate batch payload size. |
| `USER_DOCUMENT_LIMIT` | int | `50` | Maximum total papers stored per user account. |
| `INGESTION_WORKER_POLL_INTERVAL_SECONDS` | float | `2.0` | Poll interval for durable ingestion worker when idle. |
| `INGESTION_MAX_RETRIES`| int | `3` | Maximum automatic retries for interrupted or stuck jobs. |
| `INGESTION_STUCK_TIMEOUT_SECONDS` | int | `180` | Inactivity threshold before watchdog recovers a processing job. |
| `INGESTION_WATCHDOG_INTERVAL_SECONDS` | float | `15.0` | Watchdog scan frequency for stalled jobs. |

### H. Local Embedding Model

| Variable Name | Type | Default | Description & Behavior |
| :--- | :--- | :--- | :--- |
| `EMBEDDING_MODEL` | string | `BAAI/bge-small-en-v1.5` | Dense embedding model loaded from local cache. |
| `EMBEDDING_DIMENSIONS` | int | `384` | Embedding vector dimensions matching pgvector column (`vector(384)`). |
| `EMBEDDING_BATCH_SIZE` | int | `32` | Inference chunk batching size. |
| `EMBEDDING_DEVICE` | string | `cpu` | PyTorch execution device (`cpu` in container). |
| `HF_HOME` | string | `/opt/huggingface` | Hugging Face cache directory baked into Docker image. |

### I. Observability & Administration

| Variable Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ADMIN_EMAILS` | list / string | `admin@orion-assistant.ai` | Comma-separated admin email list for quota overrides. |
| `ADMIN_USER_IDS` | list / string | None | Comma-separated admin user ID list. |
| `RAG_DIAGNOSTICS_ENABLED` | bool | `true` | Enables retrieval metrics in response metadata. |

---

## 2. Frontend Web Application (Vercel Environment)

| Variable Name | Required | Default | Recommended Staging Value | Description |
| :--- | :---: | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | **YES** | `""` (empty) | `""` (empty string) | Leaving empty routes all API calls to `/api/v1` relative to the frontend domain, utilizing the `frontend/vercel.json` edge rewrite proxy to avoid cross-site cookie blocking. |

---

## 3. Production Validation Rules

The backend executes `validate_production_requirements()` in `backend/app/core/config.py` on startup whenever `ENVIRONMENT=production`. The application **fails fast and terminates** if:
1. `SECRET_KEY` is missing, shorter than 32 characters, or left as the development default.
2. `DEV_AUTH_BYPASS` is set to `true`.
3. `DATABASE_URL` targets SQLite rather than PostgreSQL.
4. `GEMINI_API_KEY` is missing, shorter than 10 characters, or contains placeholder strings (`your-gemini`).
5. `ALLOWED_ORIGINS` is empty or only contains localhost / loopback addresses.
6. `STORAGE_PROVIDER` is set to `local` instead of `s3`.
7. `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, or `S3_SECRET_ACCESS_KEY` are empty or missing.
8. The database schema revision does not match `EXPECTED_ALEMBIC_HEAD = "0003_auth_audit_events"`.


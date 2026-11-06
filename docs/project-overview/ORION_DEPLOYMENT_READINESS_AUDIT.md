# ORION — Pre-Deployment Readiness Audit
**Date:** November 2026  
**Auditor:** Senior DevOps Engineer & Cloud Deployment Architect  
**Scope:** Private Staging & Multi-User Pilot Deployment Preparation  
**Status:** READ-ONLY Assessment (No Cloud Resources Created, No Migrations Run, No Code Modified)

---

## Executive Summary

This audit assesses the deployment readiness of the **ORION AI Research Assistant** for a private staging release prior to Phase 6C execution. 

ORION's architecture consists of a **Vite + React (TypeScript) Single-Page Application (SPA)**, a **FastAPI asynchronous backend**, an **Aiven Cloud PostgreSQL 18.6 database with `pgvector`**, and an **S3-compatible object storage layer** (targeted for **Cloudflare R2**).

### Verdict: **CONDITIONAL PASS — READY WITH CONFIGURATION**

The core application code, background ingestion worker, multi-tenant isolation safeguards, Docker packaging, and database schemas are **technically ready** for containerized cloud deployment. However, **two critical architectural deployment blockers** must be addressed during configuration:
1. **Cross-Site Cookie Partitioning between Vercel and Render**: Modern browser privacy models (Chrome Privacy Sandbox, Safari ITP, Firefox Total Cookie Protection) reject or partition cross-site cookies between differing public suffixes (`*.vercel.app` and `*.onrender.com`). A unified custom domain or a Vercel API rewrite proxy is required.
2. **Public Self-Registration Exposure**: The current `POST /api/v1/auth/register` endpoint is rate-limited but allows unrestricted self-registration. A private pilot requires edge-level access control (e.g., Cloudflare Access, Vercel Deployment Protection) or an invite-code guard to prevent unauthorized resource consumption.

---

## Architecture Recommendation

### Proposed Deployment Topology

```
                         [ Pilot Researchers ]
                                  │
                                  ▼ (HTTPS)
        ┌──────────────────────────────────────────────────┐
        │                 Cloudflare DNS                   │
        │      (SSL/TLS, Edge WAF, Rate Limiting)          │
        └───────────────┬──────────────────┬───────────────┘
                        │                  │
        ┌───────────────▼────────┐ ┌───────▼────────────────┐
        │     Vercel Edge        │ │   Render Web Service   │
        │ (Static SPA Frontend)  │ │ (Containerized FastAPI)│
        │ app.orion-assistant.ai │ │ api.orion-assistant.ai │
        └───────────────┬────────┘ └───────┬────────┬───────┘
                        │ (API Proxy / CORS)│        │
                        └───────────────────┘        │
                                                     │
                        ┌────────────────────────────┼───────────────────────────┐
                        │                            │                           │
                        ▼                            ▼                           ▼
        ┌──────────────────────────────┐ ┌───────────────────────┐ ┌─────────────────────────┐
        │    Aiven PostgreSQL 18.6     │ │     Cloudflare R2     │ │    Google Gemini API    │
        │     (pgvector, SSL, PITR)    │ │(S3-Compatible Storage)│ │  (gemini-3.5-flash-lite)│
        └──────────────────────────────┘ └───────────────────────┘ └─────────────────────────┘
```

### Recommendation Evaluation

| Target Component | Proposed Provider | Evaluation & Recommendation |
| :--- | :--- | :--- |
| **Frontend** | **Vercel** | **RECOMMENDED.** Vercel offers zero-maintenance static hosting with global edge distribution, automated Git deployments, and instant preview branches. Pairs cleanly with Vite React SPA. |
| **Backend** | **Render** | **RECOMMENDED (Starter or Standard Tier).** Render provides a persistent Linux container runtime with custom Dockerfile support, automated HTTPS, and native health check integration. **Caution:** Free tier must *not* be used due to 15-minute idle spindowns and 512 MB RAM limits that cause Out-of-Memory (OOM) crashes during embedding and PDF rendering. |
| **Database** | **Aiven PostgreSQL** | **STRONGLY RECOMMENDED.** Already provisioned, configured with `pgvector`, and holding migration revision `0002_research_domain`. Provides automated point-in-time recovery (PITR) and dedicated resources. |
| **Object Storage**| **Cloudflare R2** | **STRONGLY RECOMMENDED.** 100% S3-compatible API, zero egress fees (saving substantial bandwidth costs for multi-page PDF reading and thumbnail rendering), and seamless global replication. |

---

## Detailed Evaluation by Area

### 1. Frontend Deployment Readiness (Vercel)
- **Status:** `READY` (with proxy configuration)
- **Inspection Findings:**
  - `npm run build` runs `tsc -b && vite build` and completes cleanly in **28.4s** with zero type errors.
  - Emitted assets in `frontend/dist/` are pure static HTML, CSS, JavaScript, and WOFF2 font files.
  - Client API base URL is driven by `import.meta.env.VITE_API_BASE_URL`. If unset or empty, the frontend calls relative `/api/v1` routes.
- **Recommendations:**
  - Create a `vercel.json` file to handle SPA client-side routing (`rewrites` to `/index.html`) and route `/api/:path*` directly to the Render backend service.

### 2. FastAPI Backend Deployment Readiness (Render)
- **Status:** `READY`
- **Inspection Findings:**
  - In `backend/app/main.py`, FastAPI is instantiated with a production `lifespan` handler that starts the `DurableIngestionWorker` and gracefully terminates it upon shutdown.
  - Startup validation in `backend/app/core/config.py` enforces fast failure if production settings are misconfigured.
  - Memory footprint: PyTorch (CPU-only), Hugging Face `SentenceTransformer('BAAI/bge-small-en-v1.5')`, and PyMuPDF idle at ~450 MB RAM and peak at ~750–900 MB RAM during ingestion/rendering.
- **Requirements:**
  - Minimum compute tier: **Render Starter (1 GB RAM)** or **Render Standard (2 GB RAM)**.
  - Worker concurrency: Run a single uvicorn process per container to coordinate the background ingestion worker.

### 3. Docker Image Build Readiness
- **Status:** `READY`
- **Inspection Findings:**
  - `backend/Dockerfile` employs a multi-stage build (`builder` -> `runner`).
  - CPU-only PyTorch is installed via official wheel repository (`--index-url https://download.pytorch.org/whl/cpu`), avoiding 3+ GB of CUDA GPU packages.
  - The embedding model (`BAAI/bge-small-en-v1.5`) is pre-downloaded during Docker image build into `/opt/huggingface`, preventing container boot delays.
  - Non-privileged execution: Runs under dedicated system user `orion` (UID 1000).
  - Healthcheck defined: `curl -f http://localhost:8000/health || exit 1`.
  - Verified in CI via `.github/workflows/ci.yml`.

### 4. PostgreSQL Production Connection & Alembic Migration Readiness
- **Status:** `READY`
- **Inspection Findings:**
  - Aiven PostgreSQL 18.6 connection string uses `postgresql+asyncpg://...` with mandatory SSL (`?ssl=require`).
  - Expected Alembic revision is pinned to `EXPECTED_ALEMBIC_HEAD = "0002_research_domain"` in `backend/app/db/session.py`.
  - In production (`ENVIRONMENT=production`), `verify_alembic_head()` inspects `alembic_version` and raises a `RuntimeError` if the database does not match `0002_research_domain`.
  - **Zero Database Migration Risk:** The database schema was migrated and verified during Phase 4B-2. Automatic migration execution at startup is explicitly disabled to prevent schema corruption.

### 5. S3-Compatible Storage Configuration (Cloudflare R2)
- **Status:** `READY` (Awaiting Cloudflare bucket creation)
- **Inspection Findings:**
  - `S3StorageService` in `backend/app/services/storage/s3.py` connects via `boto3` with custom `endpoint_url`, `region_name="auto"`, and virtual-host addressing compatibility.
  - `check_readiness()` performs a non-destructive, read-only `head_bucket()` check.
  - Startup check in `config.py` ensures `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` are populated when `STORAGE_PROVIDER=s3`.
  - User multi-tenant storage is isolated using object keys: `{user_id}/{document_id}/{filename}` and `{user_id}/{document_id}/renders/page_{num}.png`.

### 6. Persistent Background Ingestion Worker Behavior
- **Status:** `READY`
- **Inspection Findings:**
  - `DurableIngestionWorker` in `backend/app/services/ingestion/worker.py` coordinates document processing without external Redis/Celery dependencies.
  - **Crash Recovery:** `recover_interrupted_jobs()` runs on startup, finds documents stuck in interim states (`processing`, `validating`, `extracting`, `chunking`, `embedding`, `indexing`), deletes orphaned chunk records, increments `retry_count`, and re-queues them (up to 3 retries).
  - **Timeout Watchdog:** `recover_stuck_jobs()` runs every 15 seconds, recovering any job exceeding `INGESTION_STUCK_TIMEOUT_SECONDS = 180`.
  - **Concurrency Safety:** On PostgreSQL, queries use `SELECT ... FOR UPDATE SKIP LOCKED` so concurrent worker instances claim distinct jobs without race conditions.

### 7. HTTPS, CORS, CSRF, and Cookie Security
- **Status:** `NEEDS CONFIGURATION` (Domain / Proxy Alignment)
- **Inspection Findings:**
  - Security headers middleware in `backend/app/main.py` applies:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `X-XSS-Protection: 1; mode=block`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (when `ENVIRONMENT=production`)
  - CSRF protection: Cookie-authenticated mutations require matching `X-CSRF-Token` header and `orion_csrf` cookie verified with constant-time `secrets.compare_digest()`.
  - **Cross-Domain Cookie Constraint:** If deployed across distinct apex domains (`vercel.app` vs `onrender.com`), browsers block `SameSite=Lax` cookies. Setting `SameSite=None` with `Secure=True` works but is subject to modern browser third-party cookie restrictions.
  - **Resolution:** Either use a shared custom domain (e.g. `app.orion-assistant.ai` and `api.orion-assistant.ai` with `.orion-assistant.ai` cookie scope) or configure Vercel rewrite proxy to route `/api/*` requests same-origin.

### 8. Environment Variable Configuration
- **Status:** `READY`
- **Inspection Findings:**
  - All variables are centralized in `backend/app/core/config.py` using `pydantic-settings`.
  - Clean example templates exist in `.env.example`, `backend/.env.example`, and `frontend/.env.example`.
  - Production mode validates non-empty and non-default secrets on boot.

### 9. Logging & Error Handling
- **Status:** `READY`
- **Inspection Findings:**
  - `OrionJsonFormatter` in `backend/app/core/logging.py` formats logs as structured JSON.
  - Automatic redaction of sensitive keys: `password`, `token`, `secret`, `gemini_api_key`, `authorization`, `cookie`, `document_text`, `raw_text`, `chunk_text`, `jwt`.
  - Unhandled exceptions return generic messages in production without exposing stack traces to clients, accompanied by correlation `request_id`.

### 10. Backup and Recovery Strategy
- **Status:** `READY`
- **Inspection Findings:**
  - **Database:** Aiven PostgreSQL manages automated daily backups with continuous write-ahead logging (WAL) enabling point-in-time recovery (PITR) up to the minute.
  - **Storage:** Cloudflare R2 provides 99.999999999% (11 9's) durability across geographic zones; bucket versioning can be toggled on.
  - **Application:** Fully containerized and reproducible from Git commits.

### 11. Gemini API Key Protection & Spending Safeguards
- **Status:** `READY`
- **Inspection Findings:**
  - `GEMINI_API_KEY` resides strictly on the server backend; never exposed to frontend code or bundle assets.
  - In `backend/app/services/generation/llm.py`, quota exhaustion (HTTP 429) triggers exponential backoff and cached cooldown (`_quota_exhausted_until`) to stop outbound API flooding.
  - Deterministic fallback RAG path provides degraded answer generation if Gemini is unavailable or exhausted.
  - All LLM calls and token counts are logged to `llm_usage_records` for usage intelligence.

### 12. Private Pilot User Access Restrictions
- **Status:** `NEEDS CONFIGURATION`
- **Inspection Findings:**
  - Registration endpoint `POST /api/v1/auth/register` is open to anyone with IP rate limiting (3 registrations per minute).
  - For a confidential private staging release, public self-registration must be guarded.
  - **Resolution Options:**
    1. Edge gate: Enable Vercel Password Protection or Cloudflare Zero Trust Access on the staging URL.
    2. App gate: Temporarily restrict registration to pre-approved researcher email domains or require an invite code.

---

## Deployment Blockers & Remediation Matrix

| Blocker ID | Description | Severity | Remediation Action | Status |
| :--- | :--- | :--- | :--- | :--- |
| **BLK-01** | Cross-domain cookie rejection between Vercel and Render | **HIGH** | Configure Vercel API rewrite proxy in `vercel.json` OR configure custom subdomains under a single root domain | `NEEDS CONFIGURATION` |
| **BLK-02** | Open registration allows unauthorized user access | **HIGH** | Apply Vercel Deployment Password / Cloudflare Access for staging, or configure user invite-list check | `NEEDS CONFIGURATION` |
| **BLK-03** | Cloudflare R2 bucket and API tokens not yet provisioned | **MEDIUM** | Create R2 bucket `orion-research-documents` and generate S3 API credentials | `NEEDS CONFIGURATION` |
| **BLK-04** | Render Web Service requires paid tier for stable background worker | **MEDIUM** | Provision Render Starter ($7/mo) or Standard ($25/mo) rather than free tier to prevent 15-min spin down | `NEEDS CONFIGURATION` |

---

## Master Checklist

### Item Classification Guide
- **`READY`**: Code, container, or configuration is fully implemented, verified, and ready for deployment.
- **`NEEDS CONFIGURATION`**: Architectural feature is implemented, but platform settings, domains, or cloud resources must be configured.
- **`BLOCKED`**: Hard impediment requiring architectural modification prior to deployment.
- **`NOT VERIFIED`**: Capability could not be confirmed without performing external cloud operations.

| Category | Component / Check | Classification | Details & Notes |
| :--- | :--- | :--- | :--- |
| **Frontend** | React SPA Build (`tsc -b && vite build`) | **READY** | Builds cleanly in 28.4s, zero TypeScript errors |
| **Frontend** | Responsive Design & Navigation | **READY** | Verified across mobile, tablet, and desktop viewports |
| **Frontend** | Storage Quota Meter UI | **READY** | Displays 500 MB quota, usage bar, amber warning |
| **Frontend** | SPA Routing Configuration | **NEEDS CONFIGURATION** | Requires `vercel.json` rewrite rule for deep links |
| **Backend** | Container Dockerfile | **READY** | Multi-stage, CPU torch, pre-cached embedding model |
| **Backend** | Lifespan Startup / Shutdown | **READY** | Starts & stops ingestion worker and database pools cleanly |
| **Backend** | Production Settings Validation | **READY** | Fails fast if secret keys, origins, or S3 credentials missing |
| **Backend** | Compute Sizing (Memory / CPU) | **NEEDS CONFIGURATION** | Requires at least 1 GB RAM (Render Starter/Standard) |
| **Database** | Aiven PostgreSQL 18.6 Connectivity | **READY** | Verified over SSL with `asyncpg` |
| **Database** | pgvector Extension (`v0.8.0`) | **READY** | Extension active and tuned via `HNSW_EF_SEARCH=40` |
| **Database** | Schema Migration Status | **READY** | Pinned to `0002_research_domain`; auto-migrations disabled |
| **Database** | Multi-Tenant Relationship Isolation | **READY** | Ownership checks and composite foreign keys enforced |
| **Storage** | S3 Backend Implementation (`boto3`) | **READY** | Tested against AWS / Cloudflare R2 API models |
| **Storage** | Non-Destructive Readiness Probe | **READY** | Uses read-only `head_bucket()` without mutating data |
| **Storage** | Cloudflare R2 Bucket Provisioning | **NEEDS CONFIGURATION** | Bucket and API tokens must be created in Cloudflare |
| **Ingestion** | Single Authoritative Dispatch | **READY** | Dual-dispatch race condition eliminated in Phase 6A |
| **Ingestion** | Crash Recovery & Watchdog | **READY** | Automatic retry of interrupted jobs on container boot |
| **Security** | HTTPS / TLS Termination | **READY** | Automated via Vercel and Render edge layers |
| **Security** | Security Headers (HSTS, CSP, XFO) | **READY** | Injected via FastAPI middleware in production |
| **Security** | CSRF Double-Submit Protection | **READY** | Constant-time digest verification on all state mutations |
| **Security** | Cross-Site Cookie Policy | **NEEDS CONFIGURATION** | Requires Vercel API proxy or shared custom domain |
| **Access** | Private Pilot Access Restriction | **NEEDS CONFIGURATION** | Requires staging password or invite allowlist |
| **Monitoring**| Structured JSON Logging | **READY** | PII and credential redaction verified |
| **Monitoring**| Liveness Probe (`/health`) | **READY** | Responds 200 with environment and version metadata |
| **Monitoring**| Readiness Probe (`/ready`) | **READY** | Checks DB, pgvector, storage, and embedding model |

---

## Environment Variable Checklist

### 1. Render Backend Web Service (Environment Settings)

| Variable Name | Required | Safe Example / Description |
| :--- | :---: | :--- |
| `ENVIRONMENT` | **YES** | `production` |
| `ORION_ENV` | **YES** | `production` |
| `SECRET_KEY` | **YES** | `[64-character-cryptographically-random-hex-string]` |
| `DATABASE_URL` | **YES** | `postgresql+asyncpg://<user>:<password>@<aiven-host>:<port>/defaultdb?ssl=require` |
| `ALLOWED_ORIGINS` | **YES** | `https://app.orion-assistant.ai,https://orion-staging.vercel.app` |
| `STORAGE_PROVIDER` | **YES** | `s3` |
| `S3_ENDPOINT_URL` | **YES** | `https://<cloudflare-account-id>.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY_ID` | **YES** | `[cloudflare-r2-access-key-id]` |
| `S3_SECRET_ACCESS_KEY` | **YES** | `[cloudflare-r2-secret-access-key]` |
| `S3_BUCKET_NAME` | **YES** | `orion-research-documents` |
| `S3_REGION_NAME` | **YES** | `auto` |
| `GEMINI_API_KEY` | **YES** | `[google-ai-studio-api-key]` |
| `GEMINI_MODEL` | NO | `gemini-3.5-flash-lite` |
| `DEV_AUTH_BYPASS` | **YES** | `false` *(Critical: Must be false in production)* |
| `USER_STORAGE_QUOTA_MB` | NO | `500` *(Default per-user limit)* |
| `SESSION_COOKIE_SECURE` | NO | `true` *(Automatically set to true in production)* |
| `SESSION_COOKIE_SAMESITE` | NO | `lax` *(Set to `none` if using cross-site domains)* |
| `BACKEND_HOST` | NO | `0.0.0.0` |
| `BACKEND_PORT` | NO | `8000` |
| `HNSW_EF_SEARCH` | NO | `40` |

### 2. Vercel Frontend (Environment Settings)

| Variable Name | Required | Description |
| :--- | :---: | :--- |
| `VITE_API_BASE_URL` | **YES** | URL of backend API or proxy (e.g. `/api` or `https://api.orion-assistant.ai`) |

---

## Estimated Deployment Cost Categories (Estimates Only)

> [!NOTE]
> The following figures are planning estimates based on standard publicly available cloud pricing tiers as of Q4 2026. Actual costs will vary with usage volume and pilot duration.

| Component | Provider & Tier | Specifications | Estimated Monthly Cost |
| :--- | :--- | :--- | :--- |
| **Frontend** | Vercel (Hobby / Pro) | Global Edge CDN, Automated CI/CD | **$0.00** (Hobby) or **$20.00** (Pro) |
| **Backend** | Render (Starter Tier) | 1 vCPU, 1 GB RAM, Persistent Container | **$7.00** / month |
| **Backend** (Recommended)| Render (Standard Tier)| 1 vCPU, 2 GB RAM (Headroom for PyTorch & Ingestion) | **$25.00** / month |
| **Database** | Aiven PostgreSQL (Existing) | 1 node, pgvector, automated daily backup & PITR | **Existing provisioned resource** |
| **Object Storage**| Cloudflare R2 | 10 GB storage, 1M Class A ops, zero egress fees | **$0.00 – $1.00** / month |
| **AI Ingestion/RAG**| Google AI Studio (Gemini) | Pay-as-you-go Gemini 3.5 Flash Lite API tier | **$2.00 – $10.00** (Pilot scale) |
| **Domain & DNS** | Cloudflare DNS | Free SSL/TLS, DDoS protection, DNS management | **$0.00** |
| **TOTAL ESTIMATE** | — | **Private Pilot Staging Environment** | **~$9.00 – $36.00 / month** |

---

## Step-by-Step Staging Deployment Plan

```mermaid
flowchart TD
    Step1["1. Cloudflare R2 Bucket Provisioning"] --> Step2["2. Render Backend Web Service Setup"]
    Step2 --> Step3["3. Backend Health & Readiness Validation"]
    Step3 --> Step4["4. Vercel Frontend Deployment & Rewrites"]
    Step4 --> Step5["5. End-to-End Pilot Smoke Testing"]
    Step5 --> Step6["6. Private Access Restriction Activation"]
```

### Phase 1: Storage Provisioning (Cloudflare R2)
1. Log in to Cloudflare Dashboard -> **R2 Object Storage**.
2. Create bucket named `orion-research-documents`.
3. Enable bucket versioning to ensure protection against accidental document overwrites.
4. Generate an R2 API Token with **Object Read & Write** permissions for the `orion-research-documents` bucket.
5. Record: Endpoint URL, Access Key ID, and Secret Access Key.

### Phase 2: Backend Container Deployment (Render)
1. Connect the ORION GitHub repository to Render.
2. Select **New Web Service** -> **Docker runtime**.
3. Point to `backend/Dockerfile` as the build context.
4. Select instance type: **Starter (1 GB RAM, $7/mo)** or **Standard (2 GB RAM, $25/mo)**.
5. Configure Environment Variables as specified in the checklist above.
6. Set Health Check path to `/health`.
7. Trigger deployment and monitor the build logs (verify that `SentenceTransformer` model finishes pre-caching during image construction).

### Phase 3: Backend Health Verification
1. Verify liveness: `curl -f https://<render-service>.onrender.com/health`.
2. Verify full system readiness: `curl -f https://<render-service>.onrender.com/ready`.
3. Confirm that the JSON response returns:
   - `"database": "connected"`
   - `"pgvector": "ready (v0.8.0)"`
   - `"storage": "ready (s3)"`
   - `"embedding_model": "loaded (BAAI/bge-small-en-v1.5)"`
   - HTTP status code: `200 OK`.

### Phase 4: Frontend Deployment (Vercel)
1. In the ORION repository, create `frontend/vercel.json` with SPA routing and API proxying:
   ```json
   {
     "rewrites": [
       { "source": "/api/v1/:path*", "destination": "https://<render-service>.onrender.com/api/v1/:path*" },
       { "source": "/(.*)", "destination": "/index.html" }
     ]
   }
   ```
2. Import repository into Vercel:
   - Framework Preset: **Vite**
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
3. Set environment variable: `VITE_API_BASE_URL=""` (empty to use the same-origin Vercel rewrite proxy).
4. Deploy to Vercel staging.

### Phase 5: End-to-End Pilot Smoke Test
1. Access the Vercel staging URL.
2. Register a pilot researcher test account (`test_pilot@orion-assistant.ai`).
3. Verify that the session cookie is saved and user avatar displays in the sidebar.
4. Upload a sample multi-page academic PDF (`Attention Is All You Need`).
5. Observe the Storage Meter in the Document Library update usage stats.
6. Confirm background ingestion completes: status moves from `queued` -> `extracting` -> `chunking` -> `embedding` -> `completed`.
7. Ask an evidence-grounded research query in the Research Workspace.
8. Verify that inline citation chips open the PDF Evidence Inspector with exact page highlighting.
9. Delete the document and confirm that storage usage decrements back to 0 MB.

### Phase 6: Private Access Restriction Activation
1. Enable **Vercel Deployment Protection** (Password / SSO) or configure **Cloudflare Access** policy restricting staging URLs to pilot team members.
2. Confirm unauthenticated public traffic cannot view the application or hit registration endpoints.

---

## Private Pilot Launch Checklist

- [ ] **Infrastructure & Runtime:**
  - [ ] Render Web Service running with persistent container runtime (>= 1 GB RAM).
  - [ ] Vercel frontend deployed with SPA routing rewrites.
  - [ ] Cloudflare R2 bucket created and configured with versioning.
  - [ ] Aiven PostgreSQL connection verified with SSL active.
- [ ] **Security & Confidentiality:**
  - [ ] `DEV_AUTH_BYPASS` confirmed `false` in production environment.
  - [ ] `SECRET_KEY` is a unique 64-character random string not stored in Git.
  - [ ] `ALLOWED_ORIGINS` accurately restricted to Vercel production and staging domains.
  - [ ] Vercel deployment protection or password enabled for private staging.
  - [ ] `SESSION_COOKIE_SECURE` confirmed `true`.
- [ ] **Storage & Processing:**
  - [ ] Non-destructive storage readiness check passing on `GET /ready`.
  - [ ] 500 MB per-user storage quota active.
  - [ ] Background worker recovers cleanly on simulated container restart.
- [ ] **AI & Cost Protection:**
  - [ ] Real Gemini API key provisioned with Google Cloud budget alerts enabled.
  - [ ] Quota cooldown caching active.
  - [ ] Deterministic fallback path tested.

---

## Conclusion & State

ORION is **substantively prepared** for deployment. The container definitions, migration safeguards, multi-user isolation architecture, and background worker lifecycle are structurally sound. Executing the step-by-step configuration outlined above will yield a secure, performant, and cost-efficient staging deployment for private pilot researchers.

*Auditing complete. All actions were strictly read-only. Standing by for instructions.*


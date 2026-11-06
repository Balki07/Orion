# ORION — Production Deployment Guide

**Target Architecture:**
- **Frontend:** Vercel (Static Single-Page Application with Edge Rewrites)
- **Backend:** Render (Persistent Linux Container with Multi-Stage Dockerfile)
- **Database:** Aiven Cloud PostgreSQL 18.6 with `pgvector`
- **Object Storage:** Cloudflare R2 (S3-Compatible Object Storage)
- **AI / LLM:** Google Gemini API (`gemini-3.5-flash-lite`)

---

## 1. Architecture & Network Topology

```
                         [ Pilot Researchers ]
                                  │
                                  ▼ (HTTPS)
        ┌──────────────────────────────────────────────────┐
        │                 Cloudflare DNS                   │
        │           (Edge SSL/TLS Termination)             │
        └───────────────┬──────────────────┬───────────────┘
                        │                  │
        ┌───────────────▼────────┐ ┌───────▼────────────────┐
        │     Vercel Edge        │ │   Render Web Service   │
        │ (Static SPA Frontend)  │ │ (FastAPI + PyTorch)    │
        │  frontend/vercel.json  │ │   render.yaml (Docker) │
        └───────────────┬────────┘ └───────┬────────┬───────┘
                        │ (API Proxy / CORS)│        │
                        └───────────────────┘        │
                                                     │
                        ┌────────────────────────────┼───────────────────────────┐
                        │                            │                           │
                        ▼                            ▼                           ▼
        ┌──────────────────────────────┐ ┌───────────────────────┐ ┌─────────────────────────┐
        │    Aiven PostgreSQL 18.6     │ │     Cloudflare R2     │ │    Google Gemini API    │
        │    (pgvector, SSL, Head 0002)│ │(S3-Compatible Storage)│ │  (gemini-3.5-flash-lite)│
        └──────────────────────────────┘ └───────────────────────┘ └─────────────────────────┘
```

---

## 2. Vercel Frontend Configuration (Task 1)

### 2.1 Configuration File (`frontend/vercel.json`)
The frontend is deployed to Vercel as a Vite React Single-Page Application (SPA). To eliminate cross-site third-party cookie blocking and support seamless client-side routing, `frontend/vercel.json` defines edge rewrites and HTTP security headers:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "cleanUrls": true,
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://orion-backend.onrender.com/api/v1/:path*"
    },
    {
      "source": "/health",
      "destination": "https://orion-backend.onrender.com/health"
    },
    {
      "source": "/ready",
      "destination": "https://orion-backend.onrender.com/ready"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    },
    {
      "source": "/assets/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
      ]
    }
  ]
}
```

> [!IMPORTANT]
> When configuring the Vercel project, replace `https://orion-backend.onrender.com` in `frontend/vercel.json` with your actual Render Web Service URL.

### 2.2 Client-Side API Base Configuration
In `frontend/src/services/api.ts`:
```typescript
const VITE_API_URL = (import.meta.env?.VITE_API_BASE_URL as string | undefined) || '';
const API_BASE = VITE_API_URL ? `${VITE_API_URL.replace(/\/$/, '')}/api/v1` : '/api/v1';
```
- In Vercel, leave `VITE_API_BASE_URL=""` (empty) so all requests default to relative `/api/v1/...` routes.
- The Vercel edge rewrite proxies these requests same-origin to Render.
- **Benefits:**
  - Cookies (`orion_session` and `orion_csrf`) are treated as first-party cookies by Safari (ITP), Chrome (Privacy Sandbox), and Firefox (Total Cookie Protection).
  - `SameSite=Lax` works reliably without cross-site cookie partitioning.
  - CSRF headers (`X-CSRF-Token`) pass through the reverse proxy without modification.

---

## 3. Render Backend Configuration (Task 2)

### 3.1 Production Start Command & Dynamic Port Binding
Render dynamically assigns a port to web services using the `$PORT` environment variable (typically `10000` or `8000`).

`backend/Dockerfile` uses an `exec` shell form to expand `$PORT` while preserving direct `SIGTERM` signal propagation:
```dockerfile
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```
Additionally, `backend/app/core/config.py` defines `PORT: int | None = None` and `@property def effective_port(self) -> int` to ensure that programmatic executions (`python -m app.main`) dynamically bind to `$PORT` or `$BACKEND_PORT`.

### 3.2 Ingestion Worker Lifecycle & Graceful Shutdown
- The background ingestion worker (`DurableIngestionWorker`) starts inside FastAPI's async lifespan handler in `backend/app/main.py`.
- When Render rolls out a new deployment or restarts the service, Render sends `SIGTERM`.
- The `exec uvicorn` command passes `SIGTERM` directly to Python, invoking FastAPI's lifespan shutdown sequence:
  ```python
  logger.info(f"Shutting down {settings.APP_NAME}...")
  ingestion_worker.stop()
  await asyncio.wait_for(worker_task, timeout=3.0)
  ```
- Any document in interim states (`processing`, `validating`, `extracting`, `chunking`, `embedding`, `indexing`) when shutdown occurs is automatically detected on the next startup by `recover_interrupted_jobs()`. Partial chunks are cleared, `retry_count` is incremented, and the document is cleanly re-queued for processing.

### 3.3 Ephemeral Local Storage Independence
- In production (`ENVIRONMENT=production`), `backend/app/core/config.py` strictly mandates:
  ```python
  if self.STORAGE_PROVIDER != "s3":
      reasons.append("STORAGE_PROVIDER must be configured as 's3' in production environments.")
  ```
- Uploaded PDFs and rendered PNG page thumbnails are written directly to Cloudflare R2 using `S3StorageService` (`boto3`). No document content or persistent assets depend on local container disk.

### 3.4 Render Blueprint Specification (`render.yaml`)
Create the Render service using the declarative Blueprint file at the repository root:
```yaml
services:
  - type: web
    name: orion-backend
    runtime: docker
    plan: starter # 1 vCPU, 1 GB RAM (or Standard 2 GB for heavy PDF ingestion)
    region: oregon
    dockerContext: ./backend
    dockerfilePath: ./backend/Dockerfile
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: ORION_ENV
        value: production
      - key: BACKEND_HOST
        value: 0.0.0.0
      - key: DEV_AUTH_BYPASS
        value: "false"
      - key: STORAGE_PROVIDER
        value: s3
      - key: S3_REGION_NAME
        value: auto
      - key: S3_BUCKET_NAME
        value: orion-research-documents
      - key: USER_STORAGE_QUOTA_MB
        value: "500"
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: S3_ENDPOINT_URL
        sync: false
      - key: S3_ACCESS_KEY_ID
        sync: false
      - key: S3_SECRET_ACCESS_KEY
        sync: false
      - key: ALLOWED_ORIGINS
        sync: false
```

---

## 4. Private Pilot Security (Task 4)

### 4.1 Threat Model for Staging / Private Pilot
- **Issue with Vercel Deployment Protection Alone:** Vercel Deployment Protection (HTTP Basic Auth or Vercel login) protects the Vercel edge from unauthenticated web browsers. However, it **does not protect the Render backend API directly**. An external user who discovers the Render backend URL (`https://<service>.onrender.com`) can make direct HTTP requests (`POST /api/v1/auth/register`) to create accounts and trigger LLM queries.
- **CORS Limitations:** While `ALLOWED_ORIGINS` stops cross-origin browser scripts, it does not prevent direct API calls from `curl`, Postman, or automated scripts.

### 4.2 Security Recommendations

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Recommended Defense-in-Depth                    │
├────────────────────────────────┬───────────────────────────────────────┤
│ Layer 1: Edge Access Control   │ Vercel Deployment Protection or       │
│                                │ Cloudflare Zero Trust Access on UI    │
├────────────────────────────────┼───────────────────────────────────────┤
│ Layer 2: Origin Protection     │ Shared Cloudflare Origin Secret or    │
│                                │ Custom Domain with Cloudflare Access  │
├────────────────────────────────┼───────────────────────────────────────┤
│ Layer 3: Backend Auth Guard    │ Pre-seeded Pilot Accounts OR          │
│                                │ Staging Pilot Invite-Code Gate        │
└────────────────────────────────┴───────────────────────────────────────┘
```

#### Recommendation A: Pre-Seeded Pilot Accounts with Registration Disabled
1. Deploy the backend with `REGISTRATION_OPEN=false` (or disable the public registration tab).
2. Administratively pre-create the accounts for the verified pilot researchers directly in PostgreSQL:
   ```bash
   # Generates Argon2id hashed password and active User record
   python -m app.cli.create_user --email researcher1@university.edu --name "Dr. Researcher"
   ```
3. Invited researchers log in directly using `POST /api/v1/auth/login`. Uninvited users cannot self-register.

#### Recommendation B: Pilot Invite Code Guard
If self-registration during the pilot is desired:
- Require an optional environment variable `PILOT_INVITE_CODE` on Render.
- When `PILOT_INVITE_CODE` is set, `POST /api/v1/auth/register` validates an `invite_code` field before creating the user.
- Existing authentication (`POST /auth/login`, session cookies, JWT verification) remains completely unchanged.

---

## 5. Deployment Verification Runbook (Task 5)

Execute these verification tests immediately following staging deployment.

### 5.1 Local Docker Container Build Verification
```bash
# Build backend image locally
docker build -t orion-backend:staging -f backend/Dockerfile backend

# Verify local container runs and model pre-cache is present
docker run --rm -d --name orion-test -p 8000:8000 -e ENVIRONMENT=development orion-backend:staging
curl -f http://localhost:8000/health
docker stop orion-test
```

### 5.2 Frontend Production Build Verification
```bash
cd frontend
npm ci
npx tsc -b
npm test -- --run
npm run build
```
Verify that `frontend/dist/index.html` is generated without errors.

### 5.3 Backend Health & Readiness Checks
```bash
# 1. Liveness check (Must return 200 OK)
curl -s -i https://<render-service>.onrender.com/health

# 2. Readiness probe (Must return 200 OK with all checks ready)
curl -s https://<render-service>.onrender.com/ready | jq .
```
**Expected Response:**
```json
{
  "status": "ready",
  "environment": "production",
  "checks": {
    "database": "connected",
    "pgvector": "ready (v0.8.0)",
    "storage": "ready (s3)",
    "embedding_model": "loaded (BAAI/bge-small-en-v1.5)"
  }
}
```

### 5.4 Authentication & Session Verification
```bash
# Register pilot account
curl -s -X POST https://<render-service>.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "pilot_tester@orion.ai", "password": "SecurePassword123!", "display_name": "Pilot Tester"}' \
  -c cookies.txt | jq .

# Verify authenticated session profile
curl -s https://<render-service>.onrender.com/api/v1/auth/me \
  -b cookies.txt | jq .
```

### 5.5 Document Upload & Storage Verification
```bash
# Upload sample research PDF
curl -s -X POST https://<render-service>.onrender.com/api/v1/documents \
  -b cookies.txt \
  -H "X-CSRF-Token: $(grep orion_csrf cookies.txt | awk '{print $7}')" \
  -F "file=@tests/sample_paper.pdf" | jq .
```
Verify returned JSON includes `status: "queued"`, and storage key matches `{user_id}/{document_id}/sample_paper.pdf`.

### 5.6 Ingestion Recovery Verification
```bash
# Check document ingestion progress until status="completed"
curl -s https://<render-service>.onrender.com/api/v1/documents/<doc_id>/status \
  -b cookies.txt | jq .
```
Verify `status: "completed"`, `chunk_count > 0`, and `page_count > 0`.

### 5.7 Evidence-Grounded RAG Verification
```bash
# Ask research question grounded in uploaded paper
curl -s -X POST https://<render-service>.onrender.com/api/v1/research/ask \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $(grep orion_csrf cookies.txt | awk '{print $7}')" \
  -d '{"query": "What are the core findings of the paper?", "document_ids": ["<doc_id>"]}' | jq .
```
Verify:
- Answer contains inline citation references `[cite:1]`.
- Retrieved citations contain accurate page numbers and excerpts.

### 5.8 Storage Usage Governance Verification
```bash
curl -s https://<render-service>.onrender.com/api/v1/documents/storage-usage \
  -b cookies.txt | jq .
```
Verify returned usage matches:
- `total_quota_bytes: 524288000` (500 MB)
- `used_storage_bytes`: exact byte count of uploaded PDF
- `document_count: 1`

### 5.9 Logout & Session Revocation Verification
```bash
# Logout
curl -s -X POST https://<render-service>.onrender.com/api/v1/auth/logout \
  -b cookies.txt \
  -H "X-CSRF-Token: $(grep orion_csrf cookies.txt | awk '{print $7}')"

# Subsequent authenticated requests must be rejected (401 Unauthorized)
curl -s -i https://<render-service>.onrender.com/api/v1/auth/me \
  -b cookies.txt
```
Verify HTTP response is `401 Unauthorized`.

---

## 6. Pre-Flight Staging Checklist

Before distributing staging URLs to researchers:
- [ ] Render Web Service deployed and reporting `200 OK` on `/health` and `/ready`.
- [ ] Vercel frontend deployed and loading without console errors.
- [ ] `DEV_AUTH_BYPASS` explicitly set to `false` on Render.
- [ ] Cloudflare R2 bucket `orion-research-documents` active with versioning enabled.
- [ ] Aiven PostgreSQL connection string verified with SSL.
- [ ] Full end-to-end smoke test (Upload -> Ingestion -> RAG -> Delete) verified cleanly.


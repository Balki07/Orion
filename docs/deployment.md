# ORION — Deployment Guide

This guide details deployment options for production environments using Docker Compose, Supabase (Auth, Postgres, pgvector, Storage), and cloud container platforms (Render, Fly.io, Railway, or AWS ECS).

---

## 1. Production Architecture Overview

In a typical production setup:
1. **Frontend**: Static SPA hosted on Cloudflare Pages, Vercel, or AWS S3 + CloudFront.
2. **Backend**: Containerized FastAPI service on a Linux VPS / container host (e.g. Render, Railway, Fly.io, or AWS ECS Fargate).
3. **Database**: Supabase PostgreSQL with the `vector` extension enabled (`CREATE EXTENSION IF NOT EXISTS vector;`).
4. **Storage**: Supabase Storage bucket (`research-documents`) with authenticated or signed URL access.
5. **AI Service**: Google Gemini API via server-side API keys (`GEMINI_API_KEY`).

---

## 2. Docker Compose Deployment (Self-Hosted)

A complete `docker-compose.yml` is provided at the repository root.

### Services:
- `db`: PostgreSQL 16 with `pgvector/pgvector:pg16`
- `backend`: FastAPI app running with Uvicorn
- `frontend`: Vite React build served via Nginx reverse proxy

### Starting the Stack:
```bash
# 1. Configure production environment
cp .env.example .env
# Edit .env with your real secrets (GEMINI_API_KEY, ORION_SECRET_KEY, etc.)

# 2. Build and start containers
docker compose up -d --build

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Check status
docker compose ps
```

---

## 3. Supabase Integration Setup

### A. Database with pgvector
1. Log into your Supabase Dashboard and create a new project.
2. Navigate to **Database** → **Extensions**, search for `vector`, and enable it.
3. Obtain your connection string from **Project Settings** → **Database** (e.g., `postgresql+asyncpg://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`).
4. Set `DATABASE_URL` in your backend environment.

### B. Supabase Auth
1. Go to **Authentication** → **Providers**, ensure Email/Password is enabled.
2. Under **Project Settings** → **API**, copy `Project URL`, `anon public key`, and `JWT Secret`.
3. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_JWT_SECRET` in `.env`.

### C. Private File Storage
1. Go to **Storage** → **Buckets** → **Create Bucket**.
2. Name: `research-documents`. Toggle **Public bucket** to `OFF` (Private).
3. Set `STORAGE_PROVIDER=supabase` and `SUPABASE_STORAGE_BUCKET=research-documents`.

---

## 4. Environment Variables Checklist

Ensure these variables are configured in production:

| Variable | Description | Production Example |
| :--- | :--- | :--- |
| `ORION_ENV` | Application environment | `production` |
| `ORION_SECRET_KEY` | Hex session signing secret | `(64-char random hex string)` |
| `DATABASE_URL` | Asyncpg connection string | `postgresql+asyncpg://...` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |
| `GEMINI_MODEL` | Production LLM | `gemini-1.5-flash` |
| `STORAGE_PROVIDER` | Storage engine | `supabase` or `local` |
| `SUPABASE_URL` | Supabase project URL | `https://xyz.supabase.co` |
| `SUPABASE_ANON_KEY` | Public client key | `eyJhbGci...` |
| `SUPABASE_JWT_SECRET`| Token verification secret | `your-jwt-secret` |
| `DEV_AUTH_BYPASS` | Development auth bypass | `false` (CRITICAL) |

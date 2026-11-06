# ORION — Verified Technology Stack Specification

This document provides a comprehensive inventory of every active technology, framework, library, and tool utilized across the ORION project. Every entry has been verified against the current repository configuration files, source code, and deployment manifests.

---

## 1. Frontend Technology Stack

| Category | Technology | Version | Source / Location | Purpose & Architectural Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Framework** | React | `^19.0.0` | [`package.json`](file:///c:/Users/rbala/Documents/ORION/frontend/package.json), [`src/main.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/main.tsx) | Core declarative UI component model; modern concurrent features, suspense, and component lifecycle management. |
| **Runtime / DOM** | React DOM | `^19.0.0` | [`package.json`](file:///c:/Users/rbala/Documents/ORION/frontend/package.json) | React DOM bindings for mounting and rendering components in browser environments. |
| **Language** | TypeScript | `^5.6.3` | [`package.json`](file:///c:/Users/rbala/Documents/ORION/frontend/package.json), [`tsconfig.json`](file:///c:/Users/rbala/Documents/ORION/frontend/tsconfig.json) | Static typing, interface definitions for API contracts, domain entities, and type safety across all frontend components. |
| **Build Tool & Dev Server**| Vite | `^5.4.9` | [`vite.config.ts`](file:///c:/Users/rbala/Documents/ORION/frontend/vite.config.ts) | Fast ES module bundling, hot module replacement (HMR), production minification, and API proxying (`/api` -> backend:8000). |
| **Styling Engine** | TailwindCSS | `^3.4.14` | [`tailwind.config.js`](file:///c:/Users/rbala/Documents/ORION/frontend/tailwind.config.js), [`src/index.css`](file:///c:/Users/rbala/Documents/ORION/frontend/src/index.css) | Utility-first responsive CSS styling with custom design system tokens (colors, surfaces, fonts). |
| **CSS Preprocessing** | PostCSS & Autoprefixer | `^8.4.47` / `^10.4.20` | [`postcss.config.js`](file:///c:/Users/rbala/Documents/ORION/frontend/postcss.config.js) | Automated browser vendor prefixing and CSS pipeline optimization. |
| **CSS Class Utilities** | `clsx` & `tailwind-merge` | `^2.1.1` / `^2.5.4` | [`src/lib/utils.ts`](file:///c:/Users/rbala/Documents/ORION/frontend/src/lib/utils.ts) | Dynamic class concatenation and conflict resolution for conditional Tailwind styling (`cn()` helper). |
| **UI Primitives** | Radix UI Primitives | `^1.3.1` – `^1.5.0` | [`package.json`](file:///c:/Users/rbala/Documents/ORION/frontend/package.json) | Unstyled, accessible component primitives (`@radix-ui/react-dialog`, `@radix-ui/react-slot`, `@radix-ui/react-tooltip`). |
| **Command Palette** | `cmdk` | `^1.1.1` | [`src/components/CommandPalette.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/CommandPalette.tsx) | Fast keyboard-driven command navigation palette (`Cmd+K` / `Ctrl+K`) for switching papers, tools, and actions. |
| **Icons** | Lucide React | `^0.453.0` | [`src/components/*`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components) | Standardized vector SVG iconography used across navigation, modals, and research interfaces. |
| **Typography Fonts** | Fontsource Packages | `^5.3.0` | [`src/index.css`](file:///c:/Users/rbala/Documents/ORION/frontend/src/index.css) | Self-hosted typography: `@fontsource/instrument-sans`, `@fontsource/jetbrains-mono`, `@fontsource/newsreader`. |
| **Animations** | Motion & AutoAnimate | `^14.6.0` / `^0.10.0` | [`src/components/*`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components) | Smooth page transitions, fluid dialog entry/exit, and automatic list reordering. |
| **Server State** | TanStack React Query | `^5.59.0` | [`src/context/*`](file:///c:/Users/rbala/Documents/ORION/frontend/src/context), [`src/services/api.ts`](file:///c:/Users/rbala/Documents/ORION/frontend/src/services/api.ts) | Server state synchronization, caching, query invalidation, retry logic, and document polling. |
| **Client State** | Zustand | `^5.0.16` | [`src/store/*`](file:///c:/Users/rbala/Documents/ORION/frontend/src/store) | Lightweight client-side reactive store for UI layout state, active panel selections, and drawer controls. |
| **Form Handling** | React Hook Form & Zod | `^7.53.0` / `^3.23.8` | [`src/components/AuthModal.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/AuthModal.tsx) | Declarative form validation, error state tracking, and schema-driven payload validation. |
| **Markdown Rendering** | React Markdown & Remark GFM | `^9.0.1` / `^4.0.0` | [`src/components/ResearchInterface.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/ResearchInterface.tsx) | Renders academic LLM responses, tables, bullet points, citations, and mathematical notation. |
| **Routing** | React Router DOM | `^6.27.0` | [`src/App.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/App.tsx) | Client-side routing, navigation between research workspace, documents, notes, and usage dashboards. |
| **Notifications** | Sonner | `^2.0.8` | [`src/App.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/App.tsx) | Non-blocking, stacked toast notifications for upload status, error alerts, and action feedback. |
| **Testing Harness** | Vitest & React Testing Library | `^2.1.3` / `^16.0.1` | [`vitest.config.ts`](file:///c:/Users/rbala/Documents/ORION/frontend/vitest.config.ts), [`tests/*`](file:///c:/Users/rbala/Documents/ORION/frontend/tests) | High-speed unit and integration testing running in jsdom with full DOM assertion support. |
| **Linter** | Oxlint | `^0.10.0` | [`package.json`](file:///c:/Users/rbala/Documents/ORION/frontend/package.json) | High-performance Rust-based JavaScript/TypeScript linter enforcing clean code guidelines. |

---

## 2. Backend Technology Stack

| Category | Technology | Version | Source / Location | Purpose & Architectural Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **Runtime Language** | Python | `3.11+` | [`pyproject.toml`](file:///c:/Users/rbala/Documents/ORION/backend/pyproject.toml), [`Dockerfile`](file:///c:/Users/rbala/Documents/ORION/backend/Dockerfile) | Primary backend runtime environment, leveraging asynchronous asyncio primitives. |
| **Web Framework** | FastAPI | `>=0.111.0` | [`backend/app/main.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/main.py) | High-performance async web framework providing OpenAPI autodocumentation, dependency injection, and Pydantic validation. |
| **ASGI Web Server** | Uvicorn (standard) | `>=0.30.0` | [`backend/app/main.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/main.py) | Production ASGI server powering the FastAPI event loop with uvloop and httptools. |
| **Configuration** | Pydantic Settings | `>=2.3.0` | [`backend/app/core/config.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/core/config.py) | Type-safe centralized environment variable loading, default validation, and secret masking. |
| **Data Validation** | Pydantic v2 | `>=2.7.0` | [`backend/app/schemas/*`](file:///c:/Users/rbala/Documents/ORION/backend/app/schemas) | Request body serialization, response schema models, type coercion, and JSON schema generation. |
| **ORM & Query Engine** | SQLAlchemy (Async) | `>=2.0.30` | [`backend/app/db/session.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/db/session.py), [`backend/app/models/*`](file:///c:/Users/rbala/Documents/ORION/backend/app/models) | Asynchronous Object Relational Mapping (2.0 style syntax), connection pooling, and multi-tenant transactional safety. |
| **Database Driver** | asyncpg | `>=0.29.0` | [`pyproject.toml`](file:///c:/Users/rbala/Documents/ORION/backend/pyproject.toml) | High-performance asynchronous binary PostgreSQL client library for Python. |
| **Dev / Test Driver** | aiosqlite | `>=0.20.0` | [`pyproject.toml`](file:///c:/Users/rbala/Documents/ORION/backend/pyproject.toml) | Async SQLite driver utilized for rapid localized integration testing when PostgreSQL is bypassed. |
| **Schema Migrations** | Alembic | `>=1.13.0` | [`backend/alembic/`](file:///c:/Users/rbala/Documents/ORION/backend/alembic) | Database migration manager handling schema evolution, index definitions, and PostgreSQL constraint triggers. |
| **Vector Extension** | pgvector | `>=0.3.0` | [`backend/alembic/versions/0002_research_domain.py`](file:///c:/Users/rbala/Documents/ORION/backend/alembic/versions/0002_research_domain.py) | Native PostgreSQL vector type integration and distance operators for embedding similarity searches. |
| **Password Hashing** | Argon2-cffi | `>=23.1.0` | [`backend/app/security/password.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/security/password.py) | OWASP-recommended password hashing using Argon2id algorithm (64 MiB memory, 3 iterations, 4 parallelism). |
| **Token Handling** | PyJWT (crypto) | `>=2.8.0` | [`backend/app/security/tokens.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/security/tokens.py) | Cryptographic signing and validation of JSON Web Tokens for auth sessions. |
| **HTTP Client** | HTTPX | `>=0.27.0` | [`pyproject.toml`](file:///c:/Users/rbala/Documents/ORION/backend/pyproject.toml) | Asynchronous HTTP client used for external service integration and test client fixtures. |
| **Form Data Handling** | python-multipart | `>=0.0.9` | [`backend/app/api/v1/documents.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/api/v1/documents.py) | Parsing streaming multipart/form-data payloads during PDF document upload. |
| **Testing Suite** | Pytest & pytest-asyncio | `>=8.2.0` / `>=0.23.0` | [`backend/tests/*`](file:///c:/Users/rbala/Documents/ORION/backend/tests) | Async test runner validating API endpoints, storage isolation, auth security, and RAG pipelines. |
| **Static Code Analysis**| Ruff & Mypy | `>=0.4.0` / `>=1.10.0` | [`pyproject.toml`](file:///c:/Users/rbala/Documents/ORION/backend/pyproject.toml) | Strict code formatting, linting, import sorting, and static type checking. |

---

## 3. Database and Storage Technology

| Component | Implementation | Source / Location | Purpose & Architectural Responsibility |
| :--- | :--- | :--- | :--- |
| **Managed Relational DB** | Aiven PostgreSQL 18.6 | Remote cloud instance (`defaultdb`) | Primary persistent datastore hosting multi-tenant user accounts, sessions, document metadata, chunks, notes, and usage quotas. |
| **Vector Indexing Engine**| pgvector HNSW Index | [`backend/alembic/versions/0002_research_domain.py`](file:///c:/Users/rbala/Documents/ORION/backend/alembic/versions/0002_research_domain.py) | Hierarchical Navigable Small World (HNSW) index on 384-dimensional chunk embeddings using `vector_cosine_ops` (`m=16`, `ef_construction=64`). |
| **Database Triggers** | PostgreSQL Constraint Triggers | [`backend/alembic/versions/0002_research_domain.py`](file:///c:/Users/rbala/Documents/ORION/backend/alembic/versions/0002_research_domain.py) | Database-level tenant isolation triggers (`trg_check_document_collection_owner`, `trg_check_research_note_owner`, `trg_check_llm_usage_owner`) preventing cross-user relationship tampering. |
| **Storage Abstraction** | `StorageService` | [`backend/app/services/storage/base.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/storage/base.py) | Pluggable file storage interface decoupling the application from specific physical disk configurations. |
| **Local File Storage** | `LocalStorageBackend` | [`backend/app/services/storage/local.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/storage/local.py) | Local filesystem storage backend organizing files into user-isolated directories: `{STORAGE_LOCAL_ROOT}/{user_id}/{document_id}/...`. |
| **Cloud Object Storage** | `S3StorageBackend` | [`backend/app/services/storage/s3.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/storage/s3.py) | S3-compatible cloud object storage backend using `boto3` (`STORAGE_S3_BUCKET`, custom endpoints, AWS/MinIO compatible). |
| **Path Security** | Traversal Prevention | [`backend/app/services/storage/local.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/storage/local.py) | Path sanitization utilizing `os.path.commonpath` checks to prevent `../` directory traversal attacks. |

---

## 4. AI, Machine Learning, and RAG Pipeline

| Component | Technology / Model | Source / Location | Purpose & Architectural Responsibility |
| :--- | :--- | :--- | :--- |
| **Language Model** | Google Gemini `gemini-3.5-flash-lite` | [`backend/app/services/rag/gemini.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/gemini.py) | Primary generative LLM generating evidence-based academic research syntheses and verifiable citations. |
| **LLM SDK** | `google-genai` (`v0.1.1`) | [`backend/app/services/rag/gemini.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/gemini.py) | Official Google GenAI Python SDK communicating with the Gemini API using system instructions and structured prompting. |
| **Embedding Model** | `BAAI/bge-small-en-v1.5` | [`backend/app/services/rag/embeddings.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/embeddings.py) | 384-dimensional dense semantic embedding model from HuggingFace, executing locally on CPU/GPU via SentenceTransformers. |
| **Embedding Engine** | Sentence Transformers (`>=3.0.0`) | [`backend/app/services/rag/embeddings.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/embeddings.py) | Local PyTorch-based inference pipeline transforming text chunks into normalized cosine vectors. |
| **Vector Retrieval** | Dense Retriever (`VectorRetriever`) | [`backend/app/services/retrieval/vector.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/vector.py) | Executes tenant-filtered cosine similarity queries against PostgreSQL `chunks.embedding` using pgvector `<=>` operator. |
| **Lexical Retrieval** | BM25 Lexical Retriever | [`backend/app/services/retrieval/lexical.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/lexical.py) | Tokenizes chunks and queries to calculate BM25 scores for exact keyword, acronym, and numeric entity matching. |
| **Hybrid Rank Fusion**| Reciprocal Rank Fusion (RRF) | [`backend/app/services/retrieval/service.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/service.py) | Fuses dense vector search and BM25 lexical search rankings using formula `score = sum(1.0 / (60 + rank))` (alpha=0.5). |
| **PDF Extraction** | PyMuPDF (`fitz` `>=1.24.0`) | [`backend/app/services/ingestion/extractor.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/ingestion/extractor.py) | Extracts structured text from uploaded research papers while preserving 1-indexed page provenance and font metadata. |
| **Chunking Strategy** | `PageAwareChunker` | [`backend/app/services/ingestion/chunker.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/ingestion/chunker.py) | Splits document text into 500-token chunks with 100-token overlap while accurately tracking multi-page span boundaries (`page_numbers: list[int]`). |
| **Citation Attribution**| Academic Citation Engine | [`backend/app/services/rag/citations.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/citations.py) | Enforces strict citation formatting `[Paper Title, p. X]` and verifies claims against retrieved chunks. |

---

## 5. DevOps, Infrastructure, and Security

| Category | Technology | Source / Location | Purpose & Architectural Responsibility |
| :--- | :--- | :--- | :--- |
| **Containerization** | Docker Multi-Stage Builds | [`backend/Dockerfile`](file:///c:/Users/rbala/Documents/ORION/backend/Dockerfile), [`frontend/Dockerfile`](file:///c:/Users/rbala/Documents/ORION/frontend/Dockerfile) | Multi-stage production container builds. Backend pre-caches the BGE embedding model; Frontend compiles via Vite and serves via Alpine Nginx. |
| **Orchestration** | Docker Compose | [`docker-compose.yml`](file:///c:/Users/rbala/Documents/ORION/docker-compose.yml) | Multi-container local orchestration managing backend, frontend, local MinIO S3 object storage, and bucket provisioning. |
| **Object Storage Emulator**| MinIO | [`docker-compose.yml`](file:///c:/Users/rbala/Documents/ORION/docker-compose.yml) | S3-compatible local development object storage container (`minio/minio:RELEASE.2024-06-13T22-53-53Z`). |
| **Continuous Integration** | GitHub Actions | [`.github/workflows/ci.yml`](file:///c:/Users/rbala/Documents/ORION/.github/workflows/ci.yml) | Automated CI pipeline running backend Pytest suites, frontend Vitest suites, type checks (`tsc -b`), and Docker image builds. |
| **Health Monitoring** | Health & Readiness Probes | [`backend/app/api/v1/health.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/api/v1/health.py) | Liveness probe (`/health/live`) and readiness probe (`/health/ready`) checking database connectivity and storage mount availability. |
| **Rate Limiter** | `AuthRateLimiter` | [`backend/app/security/rate_limiter.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/security/rate_limiter.py) | In-memory sliding window rate limiter throttling brute-force authentication attacks and LLM quota abuse. |


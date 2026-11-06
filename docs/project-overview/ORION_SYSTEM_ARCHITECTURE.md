# ORION — System Architecture & Component Specification

This document details the architectural topology, communication pipelines, and component responsibilities of the ORION academic research assistant platform.

---

## 1. High-Level System Architecture Diagram

```mermaid
flowchart TD
    subgraph Client["Client Tier (Browser)"]
        UI["React 19 Frontend<br/>(Tailwind CSS, Vite, Zustand, TanStack Query)"]
    end

    subgraph Gateway["Edge & Network Security"]
        Nginx["Nginx Reverse Proxy / Static Host<br/>(Docker Alpine)"]
        CSRF["Double-Submit CSRF Guard<br/>(Header: X-CSRF-Token == Cookie: orion_csrf)"]
        RateLimit["In-Memory Sliding Window Rate Limiter<br/>(AuthRateLimiter)"]
    end

    subgraph Backend["Application Tier (FastAPI Async)"]
        FastAPI["FastAPI Web Framework (Python 3.11)"]
        AuthMid["Authentication Service<br/>(HttpOnly Cookie 'orion_session' -> Session Table)"]
        
        subgraph APIRouters["API Routers (/api/v1)"]
            R_Auth["/auth (Register, Login, Me, Logout)"]
            R_Docs["/documents (Upload, Batch, Status, Pages, Delete)"]
            R_Research["/research (Sessions, Ask, History, Feedback)"]
            R_Notes["/notes (Create, Update, List, Delete)"]
            R_Settings["/settings (LLM Quota Admin, Usage Stats)"]
            R_Health["/health (Liveness & Readiness Probes)"]
        end

        subgraph Ingestion["Ingestion & Pipeline Engine"]
            Worker["FastAPI BackgroundTasks Worker<br/>(process_document_pipeline)"]
            PDFEx["PyMuPDF (fitz) Extractor<br/>(Page Provenance & Font Weights)"]
            Chunker["PageAwareChunker<br/>(500-token / 100-overlap, Multi-page tracking)"]
            Embedder["LocalEmbedder (BAAI/bge-small-en-v1.5)<br/>(384-dim Torch / Sentence-Transformers)"]
        end

        subgraph RAGEngine["Hybrid RAG & Retrieval Engine"]
            VecRet["Dense Vector Retriever<br/>(pgvector Cosine Distance <=>)"]
            LexRet["BM25 Lexical Retriever<br/>(Exact Keyword & Token Matching)"]
            RRF["Reciprocal Rank Fusion (RRF)<br/>(score = sum(1 / (60 + rank)), alpha=0.5)"]
            GenAI["Google Gemini 3.5 Flash Lite<br/>(google-genai SDK, Academic System Instructions)"]
            CiteVal["Citation & Attribution Engine<br/>(Format: [Paper, p. X], Provenance Verification)"]
        end
    end

    subgraph DataStorage["Persistence & Storage Tier"]
        Postgres[("Aiven PostgreSQL 18.6<br/>(defaultdb with pgvector extension)")]
        HNSW["HNSW Index on chunks.embedding<br/>(m=16, ef_construction=64, vector_cosine_ops)"]
        Triggers["PostgreSQL Constraint Triggers<br/>(Database-Level Cross-Tenant Validation)"]
        StorageEngine["StorageService Abstraction"]
        LocalStorage[("Local Filesystem Storage<br/>storage/documents/{user_id}/{doc_id}/")]
        S3Storage[("S3 / MinIO Object Storage<br/>bucket: orion-documents/{user_id}/{doc_id}/")]
    end

    %% Client Communication
    UI -->|HTTPS / REST API calls| Nginx
    Nginx -->|Proxy pass :8000| CSRF
    CSRF --> RateLimit
    RateLimit --> FastAPI
    FastAPI --> AuthMid

    %% Router routing
    AuthMid --> APIRouters

    %% Document Ingestion Flow
    R_Docs -->|Store PDF binary| StorageEngine
    StorageEngine -.->|Local disk write| LocalStorage
    StorageEngine -.->|boto3 PutObject| S3Storage
    R_Docs -->|Spawn async job| Worker
    Worker --> PDFEx
    PDFEx --> Chunker
    Chunker --> Embedder
    Embedder -->|Persist chunks & 384d vectors| Postgres
    Postgres --- HNSW
    Postgres --- Triggers

    %% Research Q&A Flow
    R_Research --> VecRet
    R_Research --> LexRet
    VecRet -->|Query HNSW Index| Postgres
    LexRet -->|Query chunk content| Postgres
    VecRet --> RRF
    LexRet --> RRF
    RRF -->|Top-K Evidence Chunks| GenAI
    GenAI --> CiteVal
    CiteVal -->|Validated Cited Synthesis| R_Research
    R_Research -->|Response Payload| UI
```

---

## 2. Component Responsibility Matrix

| Subsystem | Source Component | File Location | Key Responsibilities |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | `App.tsx` | [`frontend/src/App.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/App.tsx) | Application shell, routing configuration, global modal providers, toast container (`Sonner`). |
| **Auth Context** | `AuthContext.tsx` | [`frontend/src/context/AuthContext.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/context/AuthContext.tsx) | User identity state, session bootstrap, login/logout synchronization, CSRF token persistence. |
| **API Client** | `api.ts` | [`frontend/src/services/api.ts`](file:///c:/Users/rbala/Documents/ORION/frontend/src/services/api.ts) | Fetch wrapper attaching `credentials: 'include'` and `X-CSRF-Token` headers; handles standard error envelopes. |
| **Document Modal**| `UploadModal.tsx` | [`frontend/src/components/UploadModal.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/UploadModal.tsx) | Drag-and-drop PDF upload interface, file validation, progress state, and batch submission. |
| **Research Interface**| `ResearchInterface.tsx`| [`frontend/src/components/ResearchInterface.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/ResearchInterface.tsx) | Interactive chat interface, markdown stream rendering, interactive citation pills, and PDF page viewer drawer. |
| **PDF Inspector** | `PDFViewer.tsx` | [`frontend/src/components/PDFViewer.tsx`](file:///c:/Users/rbala/Documents/ORION/frontend/src/components/PDFViewer.tsx) | Render extracted PDF page images, zoom controls, bounding boxes, and citation jump navigation. |
| **Configuration** | `config.py` | [`backend/app/core/config.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/core/config.py) | Centralized `pydantic-settings` class loading database URLs, CORS origins, cookie security flags, and model keys. |
| **Database Engine**| `session.py` | [`backend/app/db/session.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/db/session.py) | Async SQLAlchemy engine creation, connection pooling, and tenant session lifecycle injection (`get_db`). |
| **Security Service**| `auth.py` / `service.py` | [`backend/app/security/auth.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/security/auth.py) | Password verification (Argon2id), session cookie issuance (`orion_session`), CSRF validation (`compare_digest`). |
| **Rate Limiter** | `rate_limiter.py` | [`backend/app/security/rate_limiter.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/security/rate_limiter.py) | Sliding window memory rate limiter preventing brute-force logins and LLM query exhaustion. |
| **Storage Gateway**| `StorageService` | [`backend/app/services/storage/`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/storage) | Factory selecting `LocalStorageBackend` or `S3StorageBackend`; enforces tenant path containment (`commonpath`). |
| **Document Ingestion**| `service.py` | [`backend/app/services/ingestion/service.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/ingestion/service.py) | Background ingestion orchestrator: state tracking (`extracting`, `chunking`, `embedding`, `completed`, `failed`). |
| **Text Extraction**| `extractor.py` | [`backend/app/services/ingestion/extractor.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/ingestion/extractor.py) | PyMuPDF extraction preserving 1-indexed page boundaries, font size hierarchies, and heading structures. |
| **Semantic Chunker**| `chunker.py` | [`backend/app/services/ingestion/chunker.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/ingestion/chunker.py) | Sliding window chunking (500 tokens, 100 token overlap) with cross-page span preservation (`page_numbers`). |
| **Embedding Engine**| `embeddings.py` | [`backend/app/services/rag/embeddings.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/embeddings.py) | SentenceTransformers worker generating 384-dimensional normalized vectors via `BAAI/bge-small-en-v1.5`. |
| **Hybrid Retrieval**| `service.py` | [`backend/app/services/retrieval/service.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/service.py) | Coordinates dense vector search and BM25 lexical search, combining ranks via Reciprocal Rank Fusion (RRF). |
| **Dense Search** | `vector.py` | [`backend/app/services/retrieval/vector.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/vector.py) | PostgreSQL pgvector cosine similarity search (`<=>`) utilizing HNSW indexing with tenant-filtered scoping. |
| **Lexical Search**| `lexical.py` | [`backend/app/services/retrieval/lexical.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/retrieval/lexical.py) | BM25 ranker scoring exact matches for chemical formulas, author names, acronyms, and numeric statistical data. |
| **Generative LLM** | `gemini.py` | [`backend/app/services/rag/gemini.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/gemini.py) | Prompts Google Gemini with retrieved chunks, citation requirements, and token quotas; logs usage to `llm_usage_records`. |
| **Citation Verifier**| `citations.py` | [`backend/app/services/rag/citations.py`](file:///c:/Users/rbala/Documents/ORION/backend/app/services/rag/citations.py) | Parses LLM output, extracts `[Document Title, p. X]` markers, validates against context chunks, and formats UI citation nodes. |

---

## 3. End-to-End Data Flow Sequence

### 3.1. Document Ingestion Pipeline Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Researcher
    participant Frontend as React Client
    participant API as Documents API
    participant Storage as Storage Backend
    participant Worker as Background Ingestion
    participant PyMuPDF as PDF Extractor
    participant Chunker as Semantic Chunker
    participant BGE as BGE Embedder
    participant DB as Aiven PostgreSQL (pgvector)

    User->>Frontend: Select & Upload PDF (Max 32MB, 200 Pages)
    Frontend->>API: POST /api/v1/documents (FormData + CSRF Token)
    API->>API: Validate MIME (application/pdf), Magic Bytes, Size
    API->>Storage: save_file(user_id, doc_id, filename, file_bytes)
    Storage-->>API: Persisted File Path
    API->>DB: INSERT into documents (owner_id, status='pending')
    API->>Worker: Dispatch BackgroundTasks(process_document_pipeline)
    API-->>Frontend: 202 Accepted (Document Schema + status='pending')

    Worker->>DB: UPDATE documents SET status='extracting'
    Worker->>Storage: get_file(user_id, doc_id, filename)
    Storage-->>Worker: File Stream
    Worker->>PyMuPDF: Extract text, page boundaries, headings
    PyMuPDF-->>Worker: ExtractedPages (Page 1..N text & metadata)

    Worker->>DB: UPDATE documents SET status='chunking'
    Worker->>Chunker: chunk_pages(pages, max_tokens=500, overlap=100)
    Chunker-->>Worker: List[ChunkData(content, page_numbers, chunk_index)]

    Worker->>DB: UPDATE documents SET status='embedding'
    Worker->>BGE: encode([chunk.content])
    BGE-->>Worker: List[384-dimensional float vectors]
    
    Worker->>DB: Bulk INSERT INTO chunks (document_id, content, page_numbers, embedding)
    Worker->>DB: UPDATE documents SET status='completed', chunk_count=K
    Frontend->>API: GET /api/v1/documents/{id}/status (Polling)
    API-->>Frontend: 200 OK (status='completed')
```

---

### 3.2. Hybrid RAG Query & Answer Synthesis Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Researcher
    participant Frontend as React Client
    participant API as Research API
    participant DB as Aiven PostgreSQL
    participant RetService as Retrieval Service
    participant BGE as BGE Embedder
    participant Gemini as Google Gemini 3.5 Flash Lite
    participant Cite as Citation Verifier

    User->>Frontend: Enter Question: "What are the economic impacts of EPR on packaging?"
    Frontend->>API: POST /api/v1/research/sessions/{id}/ask
    API->>DB: Verify ResearchSession owner_id == current_user.id
    API->>RetService: retrieve_hybrid(query, user_id, top_k=5)

    par Dense Vector Search
        RetService->>BGE: encode(query)
        BGE-->>RetService: 384d Query Vector
        RetService->>DB: SELECT chunk_id, cosine_distance FROM chunks JOIN documents ON chunks.document_id = documents.id WHERE documents.owner_id = current_user.id ORDER BY embedding <=> query_vector LIMIT 20
        DB-->>RetService: Top 20 Dense Chunks
    and Lexical BM25 Search
        RetService->>DB: SELECT chunk_id, content FROM chunks JOIN documents ON chunks.document_id = documents.id WHERE documents.owner_id = current_user.id
        DB-->>RetService: Candidate Chunks
        RetService->>RetService: Score BM25(query_tokens, chunk_tokens)
    end

    RetService->>RetService: Reciprocal Rank Fusion (RRF: alpha=0.5, k=60)
    RetService-->>API: Top 5 Re-ranked Evidence Chunks

    API->>API: Build Context Payload & Academic System Instruction
    API->>Gemini: generate_content(prompt, context, config)
    Gemini-->>API: Generated Synthesis with raw citations
    API->>Cite: validate_and_parse_citations(text, evidence_chunks)
    Cite-->>API: Structured Citations with verified Document & Page IDs
    API->>DB: INSERT into chat_messages (session_id, role='assistant', content, citations)
    API->>DB: INSERT into llm_usage_records (user_id, prompt_tokens, candidate_tokens)
    API-->>Frontend: 200 OK (Answer Markdown, Citation Pills, Verified Page Links)
    Frontend->>User: Display Academic Answer with Interactive Sources
```


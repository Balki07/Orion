# ORION — REST API Specification

All endpoints are versioned under `/api/v1` (with system health check under `/health` and `/ready`). Requests require an `Authorization: Bearer <token>` header containing a valid Supabase JWT or development session token.

---

## 1. System & Health

### `GET /health`
- **Description**: Basic liveness probe.
- **Response**: `200 OK`
  ```json
  { "status": "ok", "version": "0.1.0", "environment": "development" }
  ```

### `GET /ready`
- **Description**: Readiness probe verifying database connectivity, embedding model readiness, and storage access.
- **Response**: `200 OK`
  ```json
  {
    "status": "ready",
    "database": "connected",
    "embedding_model": "loaded",
    "storage": "writable"
  }
  ```

---

## 2. Documents API

### `POST /api/v1/documents`
- **Description**: Upload a new research PDF for asynchronous validation, extraction, chunking, and indexing.
- **Content-Type**: `multipart/form-data` (field: `file`)
- **Query Params**: `collection_id` (optional string)
- **Response**: `201 Created`
  ```json
  {
    "id": "doc_123e4567-e89b-12d3-a456-426614174000",
    "filename": "attention_is_all_you_need.pdf",
    "file_size": 2215201,
    "status": "uploaded",
    "created_at": "2026-10-19T10:00:00Z"
  }
  ```

### `GET /api/v1/documents`
- **Description**: List all documents owned by the authenticated user with status, chunk counts, and page counts.
- **Query Params**: `collection_id` (optional), `status` (optional), `search` (optional), `limit` (default: 50), `offset` (default: 0)
- **Response**: `200 OK`
  ```json
  {
    "total": 1,
    "items": [
      {
        "id": "doc_123e4567-e89b-12d3-a456-426614174000",
        "filename": "attention_is_all_you_need.pdf",
        "file_size": 2215201,
        "page_count": 15,
        "chunk_count": 48,
        "status": "completed",
        "processing_error": null,
        "created_at": "2026-10-19T10:00:00Z"
      }
    ]
  }
  ```

### `GET /api/v1/documents/{document_id}`
- **Description**: Retrieve detailed metadata and processing statistics for a specific document.

### `GET /api/v1/documents/{document_id}/status`
- **Description**: Polling endpoint for real-time ingestion status (`uploaded`, `validating`, `extracting`, `chunking`, `embedding`, `indexing`, `completed`, `failed`).

### `GET /api/v1/documents/{document_id}/pages/{page_number}`
- **Description**: Fetch extracted text and provenance for a specific page of the document (1-indexed).

### `POST /api/v1/documents/{document_id}/retry`
- **Description**: Retry an ingestion job that encountered a transient failure.

### `DELETE /api/v1/documents/{document_id}`
- **Description**: Cascade delete document record, raw file from storage, and all associated pgvector chunk embeddings.
- **Response**: `204 No Content`

---

## 3. Collections API

### `POST /api/v1/collections`
- **Request Body**:
  ```json
  { "name": "Transformer Architectures", "description": "Core papers on attention & transformers" }
  ```
- **Response**: `201 Created`

### `GET /api/v1/collections`
- **Description**: List user collections with member document counts.

### `GET /api/v1/collections/{collection_id}`
### `PATCH /api/v1/collections/{collection_id}`
### `DELETE /api/v1/collections/{collection_id}`

---

## 4. Research & Q&A API

### `POST /api/v1/research/ask`
- **Description**: Run hybrid retrieval across user documents or collections and generate an evidence-grounded answer with verified page citations.
- **Request Body**:
  ```json
  {
    "question": "What is the computational complexity per layer of self-attention compared to recurrent layers?",
    "document_ids": ["doc_123e4567-e89b-12d3-a456-426614174000"],
    "collection_id": null,
    "session_id": null,
    "top_k": 8
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "answer": "Self-attention layers have a computational complexity per layer of O(n² · d), whereas recurrent layers require O(n · d²), where n is the sequence length and d is the representation dimensionality [cite:1].",
    "claims": [
      {
        "text": "Self-attention layers have a complexity per layer of O(n² · d).",
        "citation_ids": ["cite:1"],
        "support_status": "supported"
      }
    ],
    "citations": [
      {
        "citation_id": "cite:1",
        "document_id": "doc_123e4567-e89b-12d3-a456-426614174000",
        "filename": "attention_is_all_you_need.pdf",
        "page_numbers": [6],
        "chunk_ids": ["chunk_550e8400-e29b-41d4-a716-446655440000"],
        "excerpt": "Table 1 shows maximum path lengths, per-layer complexity and minimum number of sequential operations..."
      }
    ],
    "insufficient_evidence": false,
    "warnings": [],
    "latency_ms": {
      "retrieval": 42.1,
      "generation": 480.3,
      "total": 525.4
    }
  }
  ```

### `POST /api/v1/research/compare`
- **Description**: Compare 2 to 5 research papers side-by-side across objectives, methodology, datasets, results, limitations, and identify potential contradictions.
- **Request Body**:
  ```json
  {
    "document_ids": [
      "doc_123e4567-e89b-12d3-a456-426614174000",
      "doc_987e6543-e21b-43d2-b765-112233445566"
    ]
  }
  ```

### `GET /api/v1/research/sessions`
### `POST /api/v1/research/sessions`
### `GET /api/v1/research/sessions/{session_id}`
### `PATCH /api/v1/research/sessions/{session_id}`
### `DELETE /api/v1/research/sessions/{session_id}`

---

## 5. Notes & Synthesis API

### `POST /api/v1/notes`
- **Request Body**:
  ```json
  {
    "title": "Complexity Analysis of Transformers",
    "content": "Notes synthesized from Attention Is All You Need...",
    "source_citations": [ ... ],
    "session_id": "sess_112233"
  }
  ```

### `GET /api/v1/notes`
### `GET /api/v1/notes/{note_id}`
### `PATCH /api/v1/notes/{note_id}`
### `DELETE /api/v1/notes/{note_id}`
### `GET /api/v1/notes/{note_id}/export`
- **Description**: Export note to formatted Markdown with full bibliography and inline page citations.

---

## 6. Settings & Diagnostics API

### `GET /api/v1/settings`
- **Description**: Returns non-secret configuration (active Gemini model, embedding model, chunking parameters, storage provider, version).

### `GET /api/v1/usage`
- **Description**: Returns user's actual document counts, storage consumption, and query statistics.

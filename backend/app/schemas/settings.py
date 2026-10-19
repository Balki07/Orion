"""Settings and Usage schemas."""

from pydantic import BaseModel


class SystemSettingsResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    active_gemini_model: str
    active_embedding_model: str
    embedding_dimensions: int
    storage_provider: str
    max_upload_size_mb: int
    max_pdf_pages: int
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    hybrid_fusion_alpha: float
    reranker_enabled: bool


class UserUsageResponse(BaseModel):
    user_id: str
    document_count: int
    completed_document_count: int
    total_pages_ingested: int
    total_chunks_indexed: int
    total_storage_bytes: int
    collection_count: int
    session_count: int
    note_count: int

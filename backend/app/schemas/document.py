"""Document request and response Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    filename: str
    file_size: int
    page_count: int = 0
    status: str
    processing_error: str | None = None
    error_code: str | None = None
    extraction_warnings: list[str] | None = Field(default_factory=list)
    content_hash: str | None = None


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    items: list[DocumentResponse]


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    progress_percentage: int
    page_count: int = 0
    chunk_count: int = 0
    error: str | None = None
    error_code: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DocumentPageResponse(BaseModel):
    document_id: str
    page_number: int
    text: str
    character_count: int
    word_count: int
    has_text: bool


class BatchItemResult(BaseModel):
    filename: str
    file_size: int
    status: str  # "queued", "completed", "rejected"
    document: DocumentResponse | None = None
    error: str | None = None


class DocumentBatchResponse(BaseModel):
    total: int
    successful_count: int
    failed_count: int
    items: list[BatchItemResult]


class StorageUsageResponse(BaseModel):
    total_quota_bytes: int
    used_storage_bytes: int
    remaining_storage_bytes: int
    usage_percentage: float
    document_count: int
    quota_mb: int


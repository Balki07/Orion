"""Document request and response Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    filename: str
    file_size: int
    page_count: int = 0
    status: str
    processing_error: str | None = None
    extraction_warnings: list[str] | None = Field(default_factory=list)


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
    warnings: list[str] = Field(default_factory=list)


class DocumentPageResponse(BaseModel):
    document_id: str
    page_number: int
    text: str
    character_count: int
    word_count: int
    has_text: bool

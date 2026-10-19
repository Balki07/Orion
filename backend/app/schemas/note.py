"""Research Note schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str
    source_citations: list[dict[str, Any]] | None = Field(default_factory=list)
    session_id: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    content: str | None = None
    source_citations: list[dict[str, Any]] | None = None


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    session_id: str | None = None
    title: str
    content: str
    source_citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    total: int
    items: list[NoteResponse]


class NoteExportResponse(BaseModel):
    note_id: str
    title: str
    markdown_content: str
    filename: str

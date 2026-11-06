"""Pydantic schemas for ORION Public Demo Mode."""

from typing import Any
from pydantic import BaseModel, Field


class DemoPaperItem(BaseModel):
    """Metadata of an approved, curated demo research paper."""

    id: str = Field(..., description="Unique demo document identifier")
    filename: str = Field(..., description="Source paper filename")
    title: str = Field(..., description="Full academic paper title")
    authors: str = Field(..., description="Paper authors")
    year: int = Field(..., description="Publication year")
    journal: str = Field(..., description="Journal or publishing venue")
    doi: str | None = Field(None, description="Digital Object Identifier")
    license: str = Field(..., description="Open access license (e.g. CC BY 4.0)")
    license_url: str = Field(..., description="URL to open access license terms")
    abstract: str = Field(..., description="Paper abstract")
    total_pages: int = Field(..., description="Total page count")
    file_size_bytes: int = Field(..., description="PDF file size in bytes")


class DemoPageResponse(BaseModel):
    """Page-level extracted text and layout metadata for demo paper inspection."""

    document_id: str
    page_number: int
    total_pages: int
    text: str = Field(..., description="Extracted textual content for the page")
    has_content: bool = True


class DemoExampleQuestion(BaseModel):
    """Curated example research question with verified ground-truth citations."""

    id: str
    question: str
    category: str
    description: str
    target_papers: list[str]


class DemoCitation(BaseModel):
    """Citation reference for evidence-grounded demo answer."""

    document_id: str
    filename: str
    paper_title: str
    page_number: int
    exact_passage: str
    relevance_score: float = 1.0


class DemoAskRequest(BaseModel):
    """Inquiry payload for public demo question answering."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Academic research question (max 250 characters for public demo)",
    )
    document_ids: list[str] | None = Field(
        None,
        description="Optional list of demo document IDs to filter by. Must be in the approved allowlist.",
    )


class DemoAskResponse(BaseModel):
    """Response payload for public demo question answering."""

    answer: str
    citations: list[DemoCitation] = Field(default_factory=list)
    grounding_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_cached: bool = False
    insufficient_evidence: bool = False
    trace_id: str
    latency_ms: float
    selected_papers: list[str] = Field(default_factory=list)


class DemoStatusResponse(BaseModel):
    """Public status probe reporting demo availability and daily capacity."""

    enabled: bool
    total_papers: int
    daily_budget_total: int
    daily_budget_remaining: int
    visitor_daily_limit: int
    ip_rate_limit_per_minute: int


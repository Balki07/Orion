"""Research Q&A, Paper Comparison, and Session schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    citation_id: str = Field(..., description="Unique identifier for the citation (e.g. cite:1)")
    document_id: str = Field(..., description="Target document ID")
    filename: str = Field(..., description="Verified filename of the referenced document")
    page_numbers: list[int] = Field(default_factory=list, description="Verified page numbers in original PDF")
    chunk_ids: list[str] = Field(default_factory=list, description="Matched database chunk IDs")
    excerpt: str = Field(..., description="Exact or condensed supporting excerpt from source")


class Claim(BaseModel):
    text: str = Field(..., description="Factual claim or assertion made in the answer")
    citation_ids: list[str] = Field(default_factory=list, description="Associated citation IDs")
    support_status: Literal["supported", "partially_supported", "unsupported"] = Field(
        default="supported",
        description="Verification status of the claim against retrieved context",
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    document_ids: list[str] | None = Field(default=None, description="Specific document IDs to query")
    collection_id: str | None = Field(default=None, description="Collection ID to query")
    session_id: str | None = Field(default=None, description="Ongoing research session ID")
    top_k: int = Field(default=8, ge=1, le=30)
    enable_reranking: bool = Field(default=False)


class PipelineDiagnostics(BaseModel):
    trace_id: str
    reason_code: str
    reason_description: str
    insufficient_evidence: bool = False
    total_latency_ms: float = 0.0
    stages: list[dict] = Field(default_factory=list)


class AskResponse(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    reason_code: str | None = Field(default=None, description="Stage failure/success classification code")
    trace_id: str | None = Field(default=None, description="Correlation ID for end-to-end request tracing")
    diagnostics: PipelineDiagnostics | None = Field(default=None, description="Detailed 12-stage diagnostics")
    warnings: list[str] = Field(default_factory=list)
    session_id: str | None = None
    message_id: str | None = None
    latency_ms: dict[str, float] = Field(default_factory=dict)
    model: str | None = Field(default=None, description="Model or engine that generated the answer (null for fallback)")
    answer_path: Literal["gemini", "deterministic_fallback"] = Field(
        default="deterministic_fallback",
        description="Execution path used: gemini or deterministic_fallback",
    )
    fallback_reason: Literal["QUOTA", "MODEL_NOT_FOUND", "BAD_KEY", "KEY_NOT_LOADED", "NETWORK", "UNAVAILABLE", "OTHER"] | None = Field(
        default=None,
        description="Classified cause of fallback when answer_path is deterministic_fallback",
    )


# --- Paper Comparison Schemas ---

class PaperComparisonField(BaseModel):
    field_name: str  # "problem", "methodology", "datasets", "results", "limitations", "future_work"
    extracted_text: str
    citations: list[Citation] = Field(default_factory=list)
    is_missing: bool = False  # True if not found in source


class PaperComparisonDocumentResult(BaseModel):
    document_id: str
    filename: str
    fields: dict[str, PaperComparisonField]


class PaperComparisonRequest(BaseModel):
    document_ids: list[str] = Field(..., min_length=2, max_length=5)


class PaperComparisonResponse(BaseModel):
    documents: list[PaperComparisonDocumentResult]
    synthesis: str = Field(..., description="Evidence-grounded cross-paper comparison summary")
    contradictions: list[str] = Field(default_factory=list, description="Identified conflicting evidence/findings")
    research_gaps: list[str] = Field(default_factory=list, description="Identified open research questions")
    latency_ms: dict[str, float] = Field(default_factory=dict)


# --- Research Session Schemas ---

class SessionCreate(BaseModel):
    title: str = Field(default="New Research Session", max_length=255)


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    warnings: list[str] = Field(default_factory=list)
    latency_ms: dict[str, float] = Field(default_factory=dict)
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(SessionResponse):
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    total: int
    items: list[SessionResponse]


# --- Feedback Schema ---

class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=-1, le=1)  # +1 or -1
    comment: str | None = None

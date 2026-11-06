"""LLM Usage schemas and DTOs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LLMUsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    call_type: str
    model: str

    attempt_number: int
    max_attempts: int
    is_provider_call: bool
    status: str
    http_status_code: int | None = None
    error_category: str | None = None
    error_detail: str | None = None

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    has_usage_metadata: bool
    latency_ms: float
    created_at: datetime


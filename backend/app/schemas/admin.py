"""Admin Dashboard & Researcher Usage Analytics Pydantic Schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserOverviewStats(BaseModel):
    total_users: int = 0
    active_users_24h: int = 0
    active_users_7d: int = 0
    active_users_30d: int = 0
    new_users_today: int = 0
    new_users_this_week: int = 0
    new_users_this_month: int = 0


class LoginOverviewStats(BaseModel):
    total_logins: int = 0
    logins_today: int = 0
    logins_this_week: int = 0
    failed_logins_today: int = 0
    failed_logins_total: int = 0
    unique_users_logged_in_7d: int = 0


class DocumentOverviewStats(BaseModel):
    total_documents: int = 0
    total_storage_bytes: int = 0
    total_storage_mb: float = 0.0
    average_storage_per_user_mb: float = 0.0
    failed_documents: int = 0
    uploaded_today: int = 0
    uploaded_this_month: int = 0


class AIModelBreakdown(BaseModel):
    model_name: str
    request_count: int = 0
    total_tokens: int = 0


class AIUsageOverviewStats(BaseModel):
    total_requests: int = 0
    requests_today: int = 0
    requests_this_month: int = 0
    total_prompt_tokens: int = 0
    total_response_tokens: int = 0
    total_tokens: int = 0
    failed_requests: int = 0
    estimated_cost_usd: float = 0.0
    models: list[AIModelBreakdown] = []


class AdminOverviewResponse(BaseModel):
    users: UserOverviewStats
    logins: LoginOverviewStats
    documents: DocumentOverviewStats
    ai_usage: AIUsageOverviewStats
    server_time: datetime


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    institution: str | None = None
    status: str
    is_active: bool
    role: str = "authenticated"
    access_status: str = "pending_request"
    created_at: datetime
    last_login_at: datetime | None = None
    login_count: int = 0
    document_count: int = 0
    storage_used_bytes: int = 0
    storage_used_mb: float = 0.0
    storage_quota_mb: int = 500
    ai_request_count: int = 0
    ai_total_tokens: int = 0


class AdminUserListResponse(BaseModel):
    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class RecentLoginItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    success: bool
    ip_address: str | None = None
    user_agent: str | None = None
    failure_reason: str | None = None
    created_at: datetime


class UserDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_size_bytes: int
    status: str
    created_at: datetime


class UserSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    is_active: bool = True


class AdminUserDetailResponse(BaseModel):
    user: AdminUserSummary
    recent_logins: list[RecentLoginItem] = []
    recent_documents: list[UserDocumentSummary] = []
    active_sessions_count: int = 0
    recent_sessions: list[UserSessionSummary] = []


class TimeSeriesPoint(BaseModel):
    date: str
    count: int
    extra: dict[str, Any] | None = None


class LoginTimeSeriesPoint(BaseModel):
    date: str
    success_count: int = 0
    failure_count: int = 0


class DailyAIUsagePoint(BaseModel):
    date: str
    requests: int = 0
    tokens: int = 0
    estimated_cost_usd: float = 0.0


class AdminSystemHealth(BaseModel):
    status: str
    environment: str
    version: str
    database: dict[str, Any]
    storage: dict[str, Any]
    ingestion: dict[str, Any]
    gemini: dict[str, Any]
    timestamp: datetime


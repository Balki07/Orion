"""ORION Admin Dashboard & Researcher Analytics Endpoints.

All endpoints require administrative privileges (require_admin_user).
Access by unauthenticated users returns HTTP 401 Unauthorized.
Access by non-administrative authenticated users returns HTTP 403 Forbidden.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedUser, get_db
from app.core.config import settings
from app.core.errors import InvalidStateTransitionError
from app.db.base import generate_uuid
from app.models.access_control import AccessRequest, Invitation
from app.models.auth_event import AuthAuditEvent
from app.models.document import Document
from app.models.llm_usage import LLMUsageRecord
from app.models.session import ResearchSession
from app.models.user import User, UserSession
from app.schemas.access_control import (
    AccessRequestApprove,
    AccessRequestReject,
    AccessRequestResponse,
    InvitationCreate,
    InvitationResponse,
    UserRoleUpdate,
    UserStatusAction,
)
from app.schemas.admin import (
    AdminOverviewResponse,
    AdminSystemHealth,
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserSummary,
    AIModelBreakdown,
    AIUsageOverviewStats,
    DailyAIUsagePoint,
    DocumentOverviewStats,
    LoginOverviewStats,
    LoginTimeSeriesPoint,
    RecentLoginItem,
    TimeSeriesPoint,
    UserDocumentSummary,
    UserOverviewStats,
    UserSessionSummary,
)
from app.schemas.user import MessageResponse
from app.security.auth import require_admin_user
from app.security.service import hash_token
from app.security.state_machine import (
    AccessStatus,
    PlatformRole,
    transition_access_status,
    validate_admin_anti_lockout,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin Dashboard"],
    dependencies=[Depends(require_admin_user)],
)


def _resolve_user_role(user_id: str, email: str | None, current_role: str | None = None) -> str:
    """Determine user role strictly from admin settings and user.role column."""
    if current_role == "admin":
        return "admin"
    admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    if email and email.strip().lower() in admin_emails:
        return "admin"
    admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
    if user_id and user_id.strip() in admin_ids:
        return "admin"
    return current_role or "researcher"


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Get aggregated administrator metrics",
)
async def get_admin_overview(
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminOverviewResponse:
    """Retrieve system-wide metrics across users, logins, documents, and AI usage."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    day_24h_ago = now - timedelta(hours=24)

    # 1. Users metrics
    total_users = (await db.scalar(select(func.count(User.id)))) or 0
    new_today = (await db.scalar(select(func.count(User.id)).where(User.created_at >= today_start))) or 0
    new_week = (await db.scalar(select(func.count(User.id)).where(User.created_at >= week_start))) or 0
    new_month = (await db.scalar(select(func.count(User.id)).where(User.created_at >= month_start))) or 0

    active_24h = (
        await db.scalar(
            select(func.count(func.distinct(UserSession.user_id))).where(UserSession.created_at >= day_24h_ago)
        )
    ) or 0
    active_7d = (
        await db.scalar(
            select(func.count(func.distinct(UserSession.user_id))).where(UserSession.created_at >= week_start)
        )
    ) or 0
    active_30d = (
        await db.scalar(
            select(func.count(func.distinct(UserSession.user_id))).where(UserSession.created_at >= month_start)
        )
    ) or 0

    users_stats = UserOverviewStats(
        total_users=total_users,
        active_users_24h=active_24h,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        new_users_today=new_today,
        new_users_this_week=new_week,
        new_users_this_month=new_month,
    )

    # 2. Login metrics (from AuthAuditEvent)
    total_logins = (
        await db.scalar(
            select(func.count(AuthAuditEvent.id)).where(AuthAuditEvent.event_type == "login_success")
        )
    ) or 0
    logins_today = (
        await db.scalar(
            select(func.count(AuthAuditEvent.id)).where(
                AuthAuditEvent.event_type == "login_success",
                AuthAuditEvent.created_at >= today_start,
            )
        )
    ) or 0
    logins_week = (
        await db.scalar(
            select(func.count(AuthAuditEvent.id)).where(
                AuthAuditEvent.event_type == "login_success",
                AuthAuditEvent.created_at >= week_start,
            )
        )
    ) or 0
    failed_logins_today = (
        await db.scalar(
            select(func.count(AuthAuditEvent.id)).where(
                AuthAuditEvent.event_type == "login_failure",
                AuthAuditEvent.created_at >= today_start,
            )
        )
    ) or 0
    failed_logins_total = (
        await db.scalar(
            select(func.count(AuthAuditEvent.id)).where(AuthAuditEvent.event_type == "login_failure")
        )
    ) or 0
    unique_users_7d = (
        await db.scalar(
            select(func.count(func.distinct(AuthAuditEvent.user_id))).where(
                AuthAuditEvent.event_type == "login_success",
                AuthAuditEvent.created_at >= week_start,
            )
        )
    ) or 0

    login_stats = LoginOverviewStats(
        total_logins=total_logins,
        logins_today=logins_today,
        logins_this_week=logins_week,
        failed_logins_today=failed_logins_today,
        failed_logins_total=failed_logins_total,
        unique_users_logged_in_7d=unique_users_7d,
    )

    # 3. Document metrics
    total_docs = (
        await db.scalar(
            select(func.count(Document.id)).where(Document.status != "deleted")
        )
    ) or 0
    total_bytes = (
        await db.scalar(
            select(func.coalesce(func.sum(Document.file_size), 0)).where(Document.status != "deleted")
        )
    ) or 0
    failed_docs = (
        await db.scalar(
            select(func.count(Document.id)).where(Document.status == "failed")
        )
    ) or 0
    docs_today = (
        await db.scalar(
            select(func.count(Document.id)).where(
                Document.status != "deleted",
                Document.created_at >= today_start,
            )
        )
    ) or 0
    docs_month = (
        await db.scalar(
            select(func.count(Document.id)).where(
                Document.status != "deleted",
                Document.created_at >= month_start,
            )
        )
    ) or 0

    total_mb = round(total_bytes / (1024 * 1024), 2)
    avg_mb = round(total_mb / total_users, 2) if total_users > 0 else 0.0

    doc_stats = DocumentOverviewStats(
        total_documents=total_docs,
        total_storage_bytes=total_bytes,
        total_storage_mb=total_mb,
        average_storage_per_user_mb=avg_mb,
        failed_documents=failed_docs,
        uploaded_today=docs_today,
        uploaded_this_month=docs_month,
    )

    # 4. AI usage metrics
    total_ai_reqs = (await db.scalar(select(func.count(LLMUsageRecord.id)))) or 0
    ai_reqs_today = (
        await db.scalar(
            select(func.count(LLMUsageRecord.id)).where(LLMUsageRecord.created_at >= today_start)
        )
    ) or 0
    ai_reqs_month = (
        await db.scalar(
            select(func.count(LLMUsageRecord.id)).where(LLMUsageRecord.created_at >= month_start)
        )
    ) or 0
    prompt_tokens = (
        await db.scalar(select(func.coalesce(func.sum(LLMUsageRecord.prompt_tokens), 0)))
    ) or 0
    completion_tokens = (
        await db.scalar(select(func.coalesce(func.sum(LLMUsageRecord.completion_tokens), 0)))
    ) or 0
    total_tokens = (
        await db.scalar(select(func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0)))
    ) or 0
    failed_ai_reqs = (
        await db.scalar(
            select(func.count(LLMUsageRecord.id)).where(LLMUsageRecord.status == "failed")
        )
    ) or 0

    # Models breakdown
    model_rows = (
        await db.execute(
            select(
                LLMUsageRecord.model,
                func.count(LLMUsageRecord.id).label("req_count"),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0).label("tok_count"),
            ).group_by(LLMUsageRecord.model)
        )
    ).all()
    models_breakdown = [
        AIModelBreakdown(
            model_name=row[0] or "unknown",
            request_count=row[1],
            total_tokens=row[2],
        )
        for row in model_rows
    ]

    # Estimated cost: ~$0.0000005 per token average across standard Gemini models
    estimated_cost = round((total_tokens * 0.0000005), 4)

    ai_stats = AIUsageOverviewStats(
        total_requests=total_ai_reqs,
        requests_today=ai_reqs_today,
        requests_this_month=ai_reqs_month,
        total_prompt_tokens=prompt_tokens,
        total_response_tokens=completion_tokens,
        total_tokens=total_tokens,
        failed_requests=failed_ai_reqs,
        estimated_cost_usd=estimated_cost,
        models=models_breakdown,
    )

    return AdminOverviewResponse(
        users=users_stats,
        logins=login_stats,
        documents=doc_stats,
        ai_usage=ai_stats,
        server_time=now,
    )


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List registered researchers with usage metrics",
)
async def list_admin_users(
    search: str | None = Query(None, description="Search by email or display name"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    role_filter: str | None = Query(None, alias="role", description="Filter by role"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="Sort field: created_at, email, display_name"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserListResponse:
    """Retrieve a paginated, searchable list of researchers with batch aggregated metrics."""
    query = select(User)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            (User.email.ilike(search_pattern)) | (User.display_name.ilike(search_pattern))
        )

    if status_filter:
        query = query.where(User.status == status_filter.strip())

    # Count total matching users
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_query)) or 0

    # Sorting
    sort_col = User.created_at
    if sort_by == "email":
        sort_col = User.email
    elif sort_by == "display_name":
        sort_col = User.display_name

    if sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    user_rows = (await db.scalars(query)).all()

    user_ids = [u.id for u in user_rows]
    doc_stats_map: dict[str, tuple[int, int]] = {}
    ai_stats_map: dict[str, tuple[int, int]] = {}
    login_stats_map: dict[str, tuple[int, datetime | None]] = {}

    if user_ids:
        # Batch document stats
        doc_stmt = (
            select(
                Document.owner_id,
                func.count(Document.id).label("doc_count"),
                func.coalesce(func.sum(Document.file_size), 0).label("storage_bytes"),
            )
            .where(Document.owner_id.in_(user_ids), Document.status != "deleted")
            .group_by(Document.owner_id)
        )
        for r in (await db.execute(doc_stmt)).all():
            doc_stats_map[r[0]] = (r[1], r[2])

        # Batch AI usage stats
        ai_stmt = (
            select(
                LLMUsageRecord.user_id,
                func.count(LLMUsageRecord.id).label("req_count"),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0).label("token_count"),
            )
            .where(LLMUsageRecord.user_id.in_(user_ids))
            .group_by(LLMUsageRecord.user_id)
        )
        for r in (await db.execute(ai_stmt)).all():
            if r[0]:
                ai_stats_map[r[0]] = (r[1], r[2])

        # Batch Login stats
        login_stmt = (
            select(
                AuthAuditEvent.user_id,
                func.count(AuthAuditEvent.id).label("login_count"),
                func.max(AuthAuditEvent.created_at).label("last_login"),
            )
            .where(
                AuthAuditEvent.user_id.in_(user_ids),
                AuthAuditEvent.event_type == "login_success",
            )
            .group_by(AuthAuditEvent.user_id)
        )
        for r in (await db.execute(login_stmt)).all():
            if r[0]:
                login_stats_map[r[0]] = (r[1], r[2])

    users_list: list[AdminUserSummary] = []
    for u in user_rows:
        resolved_role = _resolve_user_role(u.id, u.email, getattr(u, "role", None))
        if role_filter and resolved_role != role_filter.strip():
            continue

        doc_count, storage_bytes = doc_stats_map.get(u.id, (0, 0))
        ai_reqs, ai_toks = ai_stats_map.get(u.id, (0, 0))
        log_count, last_log = login_stats_map.get(u.id, (0, None))

        users_list.append(
            AdminUserSummary(
                id=u.id,
                email=u.email,
                display_name=u.display_name,
                institution=u.institution,
                status=u.status,
                is_active=u.is_active,
                role=resolved_role,
                access_status="active" if resolved_role == "admin" else (getattr(u, "access_status", "pending_request") or "pending_request"),
                created_at=u.created_at,
                last_login_at=last_log,
                login_count=log_count,
                document_count=doc_count,
                storage_used_bytes=storage_bytes,
                storage_used_mb=round(storage_bytes / (1024 * 1024), 2),
                storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
                ai_request_count=ai_reqs,
                ai_total_tokens=ai_toks,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return AdminUserListResponse(
        users=users_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="Get researcher profile and activity detail",
)
async def get_admin_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserDetailResponse:
    """Retrieve comprehensive detail for a researcher including recent logins, docs, and sessions."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Researcher not found")

    # Document stats
    doc_res = (
        await db.execute(
            select(
                func.count(Document.id),
                func.coalesce(func.sum(Document.file_size), 0),
            ).where(Document.owner_id == user_id, Document.status != "deleted")
        )
    ).first()
    doc_count = doc_res[0] if doc_res else 0
    storage_bytes = doc_res[1] if doc_res else 0

    # AI stats
    ai_res = (
        await db.execute(
            select(
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
            ).where(LLMUsageRecord.user_id == user_id)
        )
    ).first()
    ai_reqs = ai_res[0] if ai_res else 0
    ai_toks = ai_res[1] if ai_res else 0

    # Login count and last login
    log_res = (
        await db.execute(
            select(
                func.count(AuthAuditEvent.id),
                func.max(AuthAuditEvent.created_at),
            ).where(AuthAuditEvent.user_id == user_id, AuthAuditEvent.event_type == "login_success")
        )
    ).first()
    login_count = log_res[0] if log_res else 0
    last_login = log_res[1] if log_res else None

    # Recent logins
    recent_logins_rows = (
        await db.scalars(
            select(AuthAuditEvent)
            .where(AuthAuditEvent.user_id == user_id)
            .order_by(AuthAuditEvent.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_logins = [
        RecentLoginItem(
            id=evt.id,
            event_type=evt.event_type,
            success=evt.success,
            ip_address=evt.ip_address,
            user_agent=evt.user_agent,
            failure_reason=evt.failure_reason,
            created_at=evt.created_at,
        )
        for evt in recent_logins_rows
    ]

    # Recent documents
    recent_docs_rows = (
        await db.scalars(
            select(Document)
            .where(Document.owner_id == user_id, Document.status != "deleted")
            .order_by(Document.created_at.desc())
            .limit(10)
        )
    ).all()
    recent_docs = [
        UserDocumentSummary(
            id=d.id,
            title=d.filename,
            file_size_bytes=d.file_size,
            status=d.status,
            created_at=d.created_at,
        )
        for d in recent_docs_rows
    ]

    # Active sessions
    now_utc = datetime.now(UTC)
    user_sessions = (
        await db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.created_at.desc())
        )
    ).all()

    def _session_active(s: UserSession) -> bool:
        if s.is_revoked:
            return False
        exp = s.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return exp > now_utc

    active_sessions_count = sum(1 for s in user_sessions if _session_active(s))
    recent_sessions = [
        UserSessionSummary(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_active=_session_active(s),
        )
        for s in user_sessions[:5]
    ]

    detail_role = _resolve_user_role(user.id, user.email, getattr(user, "role", None))
    user_summary = AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=detail_role,
        access_status="active" if detail_role == "admin" else (getattr(user, "access_status", "pending_request") or "pending_request"),
        created_at=user.created_at,
        last_login_at=last_login,
        login_count=login_count,
        document_count=doc_count,
        storage_used_bytes=storage_bytes,
        storage_used_mb=round(storage_bytes / (1024 * 1024), 2),
        storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
        ai_request_count=ai_reqs,
        ai_total_tokens=ai_toks,
    )

    return AdminUserDetailResponse(
        user=user_summary,
        recent_logins=recent_logins,
        recent_documents=recent_docs,
        active_sessions_count=active_sessions_count,
        recent_sessions=recent_sessions,
    )


@router.get(
    "/users/{user_id}/activity",
    summary="Get chronological activity events for a researcher",
)
async def get_admin_user_activity(
    user_id: str,
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[dict[str, Any]]:
    """Retrieve a unified chronological activity timeline for a single user."""
    # Check user existence
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Researcher not found")

    events: list[dict[str, Any]] = []

    # 1. Auth events
    auth_evts = (
        await db.scalars(
            select(AuthAuditEvent)
            .where(AuthAuditEvent.user_id == user_id)
            .order_by(AuthAuditEvent.created_at.desc())
            .limit(limit)
        )
    ).all()
    for e in auth_evts:
        events.append(
            {
                "id": e.id,
                "type": "auth",
                "action": e.event_type,
                "success": e.success,
                "ip_address": e.ip_address,
                "timestamp": e.created_at.isoformat(),
                "details": {"failure_reason": e.failure_reason} if not e.success else {},
            }
        )

    # 2. Document upload events
    docs = (
        await db.scalars(
            select(Document)
            .where(Document.owner_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
    ).all()
    for d in docs:
        events.append(
            {
                "id": d.id,
                "type": "document",
                "action": "document_uploaded",
                "success": d.status != "failed",
                "timestamp": d.created_at.isoformat(),
                "details": {
                    "filename": d.filename,
                    "file_size": d.file_size,
                    "status": d.status,
                },
            }
        )

    # 3. AI interaction events
    ai_records = (
        await db.scalars(
            select(LLMUsageRecord)
            .where(LLMUsageRecord.user_id == user_id)
            .order_by(LLMUsageRecord.created_at.desc())
            .limit(limit)
        )
    ).all()
    for r in ai_records:
        events.append(
            {
                "id": r.id,
                "type": "ai_query",
                "action": r.call_type,
                "success": r.status == "success",
                "timestamp": r.created_at.isoformat(),
                "details": {
                    "model": r.model,
                    "tokens": r.total_tokens,
                    "latency_ms": r.latency_ms,
                    "status": r.status,
                },
            }
        )

    # Sort unified events descending by timestamp
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events[:limit]


@router.get(
    "/users/{user_id}/usage",
    summary="Get storage and quota breakdown for a researcher",
)
async def get_admin_user_usage(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> dict[str, Any]:
    """Retrieve detailed storage, quota compliance, and LLM usage breakdown for a user."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Researcher not found")

    # Document storage breakdown
    doc_res = (
        await db.execute(
            select(
                func.count(Document.id),
                func.coalesce(func.sum(Document.file_size), 0),
            ).where(Document.owner_id == user_id, Document.status != "deleted")
        )
    ).first()
    doc_count = doc_res[0] if doc_res else 0
    storage_bytes = doc_res[1] if doc_res else 0
    storage_mb = round(storage_bytes / (1024 * 1024), 2)
    quota_mb = settings.USER_STORAGE_QUOTA_MB
    percent_used = round((storage_mb / quota_mb) * 100, 1) if quota_mb > 0 else 0.0

    # Documents by status
    status_rows = (
        await db.execute(
            select(Document.status, func.count(Document.id))
            .where(Document.owner_id == user_id)
            .group_by(Document.status)
        )
    ).all()
    status_breakdown = {row[0]: row[1] for row in status_rows}

    # AI usage breakdown by model
    model_rows = (
        await db.execute(
            select(
                LLMUsageRecord.model,
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
            )
            .where(LLMUsageRecord.user_id == user_id)
            .group_by(LLMUsageRecord.model)
        )
    ).all()
    model_breakdown = [
        {"model": row[0], "requests": row[1], "tokens": row[2]} for row in model_rows
    ]

    return {
        "user_id": user.id,
        "email": user.email,
        "storage": {
            "used_bytes": storage_bytes,
            "used_mb": storage_mb,
            "quota_mb": quota_mb,
            "quota_percent_used": min(percent_used, 100.0),
            "documents_count": doc_count,
            "by_status": status_breakdown,
        },
        "ai_usage": {
            "models": model_breakdown,
        },
    }


@router.get(
    "/analytics/registrations",
    response_model=list[TimeSeriesPoint],
    summary="Daily registration counts (past 30 days)",
)
async def get_registration_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[TimeSeriesPoint]:
    """Retrieve daily user registration counts for trend visualization."""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    users = (
        await db.scalars(
            select(User.created_at).where(User.created_at >= start_date)
        )
    ).all()

    # Aggregate counts by YYYY-MM-DD
    counts: dict[str, int] = {}
    for i in range(days):
        d = (start_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        counts[d] = 0

    for created in users:
        d = created.strftime("%Y-%m-%d")
        if d in counts:
            counts[d] += 1

    return [TimeSeriesPoint(date=k, count=v) for k, v in sorted(counts.items())]


@router.get(
    "/analytics/logins",
    response_model=list[LoginTimeSeriesPoint],
    summary="Daily login events (past 30 days)",
)
async def get_login_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[LoginTimeSeriesPoint]:
    """Retrieve daily successful and failed login counts for security and engagement monitoring."""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    events = (
        await db.execute(
            select(
                AuthAuditEvent.created_at,
                AuthAuditEvent.event_type,
                AuthAuditEvent.success,
            ).where(
                AuthAuditEvent.created_at >= start_date,
                AuthAuditEvent.event_type.in_(["login_success", "login_failure"]),
            )
        )
    ).all()

    points_map: dict[str, dict[str, int]] = {}
    for i in range(days):
        d = (start_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        points_map[d] = {"success": 0, "failure": 0}

    for created_at, ev_type, success in events:
        d = created_at.strftime("%Y-%m-%d")
        if d in points_map:
            if ev_type == "login_success" or success:
                points_map[d]["success"] += 1
            else:
                points_map[d]["failure"] += 1

    return [
        LoginTimeSeriesPoint(
            date=k,
            success_count=v["success"],
            failure_count=v["failure"],
        )
        for k, v in sorted(points_map.items())
    ]


@router.get(
    "/analytics/documents",
    response_model=list[TimeSeriesPoint],
    summary="Daily document upload counts (past 30 days)",
)
async def get_document_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[TimeSeriesPoint]:
    """Retrieve daily document upload counts."""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    docs = (
        await db.scalars(
            select(Document.created_at).where(
                Document.created_at >= start_date,
                Document.status != "deleted",
            )
        )
    ).all()

    counts: dict[str, int] = {}
    for i in range(days):
        d = (start_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        counts[d] = 0

    for created in docs:
        d = created.strftime("%Y-%m-%d")
        if d in counts:
            counts[d] += 1

    return [TimeSeriesPoint(date=k, count=v) for k, v in sorted(counts.items())]


@router.get(
    "/analytics/ai-usage",
    response_model=list[DailyAIUsagePoint],
    summary="Daily AI requests and token volume (past 30 days)",
)
async def get_ai_usage_analytics(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[DailyAIUsagePoint]:
    """Retrieve daily AI request counts and token volume."""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    records = (
        await db.execute(
            select(
                LLMUsageRecord.created_at,
                LLMUsageRecord.total_tokens,
            ).where(LLMUsageRecord.created_at >= start_date)
        )
    ).all()

    points_map: dict[str, dict[str, Any]] = {}
    for i in range(days):
        d = (start_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        points_map[d] = {"requests": 0, "tokens": 0}

    for created, tokens in records:
        d = created.strftime("%Y-%m-%d")
        if d in points_map:
            points_map[d]["requests"] += 1
            points_map[d]["tokens"] += (tokens or 0)

    result: list[DailyAIUsagePoint] = []
    for d, data in sorted(points_map.items()):
        toks = data["tokens"]
        cost = round(toks * 0.0000005, 4)
        result.append(
            DailyAIUsagePoint(
                date=d,
                requests=data["requests"],
                tokens=toks,
                estimated_cost_usd=cost,
            )
        )
    return result


@router.get(
    "/system-health",
    response_model=AdminSystemHealth,
    summary="Safe system and infrastructure health status",
)
async def get_admin_system_health(
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminSystemHealth:
    """Inspect application and infrastructure readiness without exposing secrets or credentials."""
    # 1. Database check
    db_healthy = False
    db_dialect = "unknown"
    pgvector_ready = False
    try:
        res = await db.execute(text("SELECT 1"))
        if res.scalar() == 1:
            db_healthy = True
        bind = db.get_bind()
        db_dialect = bind.dialect.name if bind else "unknown"
        if db_dialect == "postgresql":
            ext_res = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            pgvector_ready = ext_res.scalar() == 1
        else:
            pgvector_ready = True  # SQLite fallback mode
    except Exception as e:
        db_healthy = False

    # 2. Storage check
    storage_provider = getattr(settings, "STORAGE_PROVIDER", "local")
    storage_ready = True
    storage_info = {
        "provider": storage_provider,
        "user_quota_mb": settings.USER_STORAGE_QUOTA_MB,
        "ready": storage_ready,
    }

    # 3. Ingestion worker check
    worker_enabled = getattr(settings, "DURABLE_INGESTION_WORKER_ENABLED", True)
    concurrency = getattr(settings, "INGESTION_WORKER_CONCURRENCY", 2)
    ingestion_info = {
        "durable_worker_enabled": worker_enabled,
        "concurrency": concurrency,
        "status": "active" if worker_enabled else "disabled",
    }

    # 4. Gemini configuration check (SAFE: NEVER EXPOSE API KEY)
    gemini_key_configured = bool(getattr(settings, "GEMINI_API_KEY", None))
    gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    gemini_rpm = getattr(settings, "GEMINI_RPM_LIMIT", 60)
    gemini_info = {
        "model": gemini_model,
        "api_key_configured": gemini_key_configured,
        "rpm_limit": gemini_rpm,
        "status": "ready" if gemini_key_configured else "unconfigured",
    }

    overall_status = "healthy" if db_healthy else "degraded"

    return AdminSystemHealth(
        status=overall_status,
        environment=settings.ORION_ENV,
        version="1.0.0",
        database={
            "healthy": db_healthy,
            "dialect": db_dialect,
            "pgvector_ready": pgvector_ready,
        },
        storage=storage_info,
        ingestion=ingestion_info,
        gemini=gemini_info,
        timestamp=datetime.now(UTC),
    )


# --- Researcher Access Control & User Administration Endpoints ---


@router.post(
    "/users/{user_id}/revoke",
    response_model=AdminUserSummary,
    summary="Revoke researcher workspace access",
)
async def revoke_user_access(
    user_id: str,
    payload: UserStatusAction,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserSummary:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.role == "admin" or user.id == admin.id:
        await validate_admin_anti_lockout(db, user, "revoke", admin.id)

    await transition_access_status(
        session=db,
        target_user=user,
        new_status=AccessStatus.REVOKED,
        actor_id=admin.id,
        actor_role="admin",
        reason=payload.reason or "Revoked by administrator",
    )
    await db.commit()
    await db.refresh(user)

    resolved_role = _resolve_user_role(user.id, user.email, user.role)
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=resolved_role,
        access_status=user.access_status,
        created_at=user.created_at,
        storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
    )


@router.post(
    "/users/{user_id}/reactivate",
    response_model=AdminUserSummary,
    summary="Reactivate revoked researcher access",
)
async def reactivate_user_access(
    user_id: str,
    payload: UserStatusAction,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserSummary:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await transition_access_status(
        session=db,
        target_user=user,
        new_status=AccessStatus.ACTIVE,
        actor_id=admin.id,
        actor_role="admin",
        reason=payload.reason or "Reactivated by administrator",
    )
    await db.commit()
    await db.refresh(user)

    resolved_role = _resolve_user_role(user.id, user.email, user.role)
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=resolved_role,
        access_status=user.access_status,
        created_at=user.created_at,
        storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
    )


@router.post(
    "/users/{user_id}/direct-activate",
    response_model=AdminUserSummary,
    summary="Directly activate pending user account",
)
async def direct_activate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserSummary:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await transition_access_status(
        session=db,
        target_user=user,
        new_status=AccessStatus.ACTIVE,
        actor_id=admin.id,
        actor_role="admin",
        reason="Directly activated by administrator",
    )
    await db.commit()
    await db.refresh(user)

    resolved_role = _resolve_user_role(user.id, user.email, user.role)
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=resolved_role,
        access_status=user.access_status,
        created_at=user.created_at,
        storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
    )


@router.post(
    "/users/{user_id}/role",
    response_model=AdminUserSummary,
    summary="Update platform role with anti-lockout safeguards",
)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AdminUserSummary:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.role == "admin" and payload.role != "admin":
        await validate_admin_anti_lockout(db, user, "demote", admin.id)

    old_role = user.role
    user.role = payload.role
    if user.role == "admin":
        user.access_status = AccessStatus.ACTIVE.value

    import json
    audit_evt = AuthAuditEvent(
        id=generate_uuid("evt"),
        user_id=user.id,
        email=user.email,
        event_type="role_updated",
        success=True,
        actor_id=admin.id,
        details=json.dumps({"old_role": old_role, "new_role": user.role}),
    )
    db.add(audit_evt)
    await db.commit()
    await db.refresh(user)

    resolved_role = _resolve_user_role(user.id, user.email, user.role)
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        institution=user.institution,
        status=user.status,
        is_active=user.is_active,
        role=resolved_role,
        access_status="active" if resolved_role == "admin" else user.access_status,
        created_at=user.created_at,
        storage_quota_mb=settings.USER_STORAGE_QUOTA_MB,
    )


@router.get(
    "/access-requests",
    response_model=list[AccessRequestResponse],
    summary="List researcher access requests",
)
async def list_access_requests(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[AccessRequestResponse]:
    stmt = (
        select(AccessRequest, User.email, User.display_name)
        .join(User, AccessRequest.user_id == User.id)
        .order_by(AccessRequest.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(AccessRequest.status == status_filter.strip())

    results = (await db.execute(stmt)).all()
    out: list[AccessRequestResponse] = []
    for req, email, display_name in results:
        out.append(
            AccessRequestResponse(
                id=req.id,
                user_id=req.user_id,
                user_email=email,
                user_display_name=display_name,
                institution=req.institution,
                research_purpose=req.research_purpose,
                intended_data_types=req.intended_data_types,
                status=req.status,
                reviewed_by=req.reviewed_by,
                reviewed_at=req.reviewed_at,
                rejection_reason=req.rejection_reason,
                created_at=req.created_at,
                updated_at=req.updated_at,
            )
        )
    return out


@router.post(
    "/access-requests/{request_id}/approve",
    response_model=InvitationResponse,
    summary="Approve access request and generate one-time invitation token",
)
async def approve_access_request(
    request_id: str,
    payload: AccessRequestApprove,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> InvitationResponse:
    req = await db.get(AccessRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found.")
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Access request is already '{req.status}'.",
        )

    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    await transition_access_status(
        session=db,
        target_user=user,
        new_status=AccessStatus.APPROVED_INVITATION_PENDING,
        actor_id=admin.id,
        actor_role="admin",
        reason="Access request approved by administrator",
        metadata={"request_id": req.id},
    )

    now_utc = datetime.now(UTC)
    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = now_utc

    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)
    expires_at = now_utc + timedelta(days=payload.expires_in_days)

    inv = Invitation(
        id=generate_uuid("inv"),
        token_hash=token_h,
        user_id=user.id,
        access_request_id=req.id,
        created_by=admin.id,
        expires_at=expires_at,
        is_redeemed=False,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    return InvitationResponse(
        id=inv.id,
        user_id=inv.user_id,
        user_email=user.email,
        invitation_token=raw_token,
        expires_at=inv.expires_at,
        is_redeemed=inv.is_redeemed,
        redeemed_at=inv.redeemed_at,
        created_at=inv.created_at,
    )


@router.post(
    "/access-requests/{request_id}/reject",
    response_model=AccessRequestResponse,
    summary="Reject researcher access request",
)
async def reject_access_request(
    request_id: str,
    payload: AccessRequestReject,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> AccessRequestResponse:
    req = await db.get(AccessRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found.")
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Access request is already '{req.status}'.",
        )

    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    await transition_access_status(
        session=db,
        target_user=user,
        new_status=AccessStatus.REJECTED,
        actor_id=admin.id,
        actor_role="admin",
        reason=payload.reason,
        metadata={"request_id": req.id},
    )

    now_utc = datetime.now(UTC)
    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = now_utc
    req.rejection_reason = payload.reason

    await db.commit()
    await db.refresh(req)

    return AccessRequestResponse(
        id=req.id,
        user_id=req.user_id,
        user_email=user.email,
        user_display_name=user.display_name,
        institution=req.institution,
        research_purpose=req.research_purpose,
        intended_data_types=req.intended_data_types,
        status=req.status,
        reviewed_by=req.reviewed_by,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.get(
    "/invitations",
    response_model=list[InvitationResponse],
    summary="List researcher invitations",
)
async def list_invitations(
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> list[InvitationResponse]:
    stmt = (
        select(Invitation, User.email)
        .join(User, Invitation.user_id == User.id)
        .order_by(Invitation.created_at.desc())
    )
    results = (await db.execute(stmt)).all()
    out: list[InvitationResponse] = []
    for inv, email in results:
        out.append(
            InvitationResponse(
                id=inv.id,
                user_id=inv.user_id,
                user_email=email,
                invitation_token=None,
                expires_at=inv.expires_at,
                is_redeemed=inv.is_redeemed,
                redeemed_at=inv.redeemed_at,
                created_at=inv.created_at,
            )
        )
    return out


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Directly issue a researcher invitation token",
)
async def create_invitation(
    payload: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> InvitationResponse:
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    now_utc = datetime.now(UTC)
    raw_token = secrets.token_urlsafe(32)
    token_h = hash_token(raw_token)
    expires_at = now_utc + timedelta(days=payload.expires_in_days)

    if user.access_status in (AccessStatus.PENDING_REQUEST.value, AccessStatus.REQUEST_SUBMITTED.value):
        user.access_status = AccessStatus.APPROVED_INVITATION_PENDING.value

    inv = Invitation(
        id=generate_uuid("inv"),
        token_hash=token_h,
        user_id=user.id,
        created_by=admin.id,
        expires_at=expires_at,
        is_redeemed=False,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    return InvitationResponse(
        id=inv.id,
        user_id=inv.user_id,
        user_email=user.email,
        invitation_token=raw_token,
        expires_at=inv.expires_at,
        is_redeemed=inv.is_redeemed,
        redeemed_at=inv.redeemed_at,
        created_at=inv.created_at,
    )


@router.delete(
    "/invitations/{invitation_id}",
    response_model=MessageResponse,
    summary="Revoke or delete an unredeemed invitation",
)
async def delete_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin_user),
) -> MessageResponse:
    inv = await db.get(Invitation, invitation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    user = await db.get(User, inv.user_id)
    if user and user.access_status == AccessStatus.APPROVED_INVITATION_PENDING.value:
        other_inv_stmt = select(func.count(Invitation.id)).where(
            Invitation.user_id == user.id,
            Invitation.id != inv.id,
            Invitation.is_redeemed.is_(False),
            Invitation.expires_at > datetime.now(UTC),
        )
        other_cnt = (await db.scalar(other_inv_stmt)) or 0
        if other_cnt == 0:
            user.access_status = AccessStatus.REVOKED.value

    await db.delete(inv)
    await db.commit()
    return MessageResponse(message="Invitation successfully cancelled.")

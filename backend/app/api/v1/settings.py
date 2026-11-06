"""Settings and Usage diagnostics REST API."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedUser,
    get_db,
    require_active_researcher,
    require_admin_user,
)
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.collection import Collection
from app.models.document import Document
from app.models.note import ResearchNote
from app.models.session import ResearchSession
from app.schemas.llm_quota import (
    LLMQuestionBudgetEstimate,
    LLMQuotaConfigUpdate,
    LLMQuotaResponse,
)
from app.schemas.settings import SystemSettingsResponse, UserUsageResponse
from app.services.generation.quota_service import (
    get_question_budget_estimate,
    get_quota_status,
    update_quota_config,
)

router = APIRouter(tags=["Settings & Diagnostics"])


@router.get("/settings", response_model=SystemSettingsResponse)
async def get_researcher_settings(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
) -> SystemSettingsResponse:
    """Retrieve legitimate researcher workspace settings and limits (active researchers and admins)."""
    return SystemSettingsResponse(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.ORION_ENV,
        active_gemini_model=settings.GEMINI_MODEL,
        active_embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimensions=settings.EMBEDDING_DIMENSIONS,
        storage_provider=settings.STORAGE_PROVIDER,
        max_upload_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        max_pdf_pages=settings.MAX_PDF_PAGES,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        retrieval_top_k=settings.RETRIEVAL_TOP_K,
        hybrid_fusion_alpha=settings.HYBRID_FUSION_ALPHA,
        reranker_enabled=settings.RERANKER_ENABLED,
    )


@router.get("/settings/system", response_model=SystemSettingsResponse)
@router.get("/system/settings", response_model=SystemSettingsResponse)
async def get_system_diagnostics(
    admin_user: AuthenticatedUser = Depends(require_admin_user),
) -> SystemSettingsResponse:
    """Retrieve comprehensive system diagnostics and AI model configurations (administrators only)."""
    return SystemSettingsResponse(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.ORION_ENV,
        active_gemini_model=settings.GEMINI_MODEL,
        active_embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimensions=settings.EMBEDDING_DIMENSIONS,
        storage_provider=settings.STORAGE_PROVIDER,
        max_upload_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        max_pdf_pages=settings.MAX_PDF_PAGES,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        retrieval_top_k=settings.RETRIEVAL_TOP_K,
        hybrid_fusion_alpha=settings.HYBRID_FUSION_ALPHA,
        reranker_enabled=settings.RERANKER_ENABLED,
    )


@router.get("/usage", response_model=UserUsageResponse)
async def get_user_usage(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve real measured usage statistics for authenticated user's workspace."""
    # 1. Document counts and storage
    doc_stmt = select(
        func.count(Document.id),
        func.coalesce(func.sum(Document.page_count), 0),
        func.coalesce(func.sum(Document.file_size), 0),
    ).where(Document.owner_id == current_user.id)
    doc_res = await db.execute(doc_stmt)
    doc_count, total_pages, total_bytes = doc_res.one()

    # Completed documents
    comp_stmt = select(func.count(Document.id)).where(
        Document.owner_id == current_user.id,
        Document.status == "completed",
    )
    comp_res = await db.execute(comp_stmt)
    comp_count = comp_res.scalar() or 0

    # Chunks count
    chunk_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.owner_id == current_user.id)
    )
    chunk_res = await db.execute(chunk_stmt)
    chunk_count = chunk_res.scalar() or 0

    # Collections, sessions, notes count
    coll_stmt = select(func.count(Collection.id)).where(Collection.owner_id == current_user.id)
    coll_res = await db.execute(coll_stmt)
    coll_count = coll_res.scalar() or 0

    sess_stmt = select(func.count(ResearchSession.id)).where(ResearchSession.owner_id == current_user.id)
    sess_res = await db.execute(sess_stmt)
    sess_count = sess_res.scalar() or 0

    note_stmt = select(func.count(ResearchNote.id)).where(ResearchNote.owner_id == current_user.id)
    note_res = await db.execute(note_stmt)
    note_count = note_res.scalar() or 0

    return UserUsageResponse(
        user_id=current_user.id,
        document_count=doc_count,
        completed_document_count=comp_count,
        total_pages_ingested=total_pages,
        total_chunks_indexed=chunk_count,
        total_storage_bytes=total_bytes,
        collection_count=coll_count,
        session_count=sess_count,
        note_count=note_count,
    )


@router.get("/settings/llm-quota", response_model=LLMQuotaResponse)
@router.get("/llm-quota", response_model=LLMQuotaResponse, include_in_schema=False)
async def get_llm_quota(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve active model configured reference quota limits and real-time utilization metrics."""
    return await get_quota_status(db)


@router.get("/settings/llm-quota/estimate", response_model=LLMQuestionBudgetEstimate)
@router.get("/llm-quota/estimate", response_model=LLMQuestionBudgetEstimate, include_in_schema=False)
async def get_llm_quota_estimate(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve estimated question budget and quota limit projections."""
    return await get_question_budget_estimate(db)


@router.put("/settings/llm-quota", response_model=LLMQuotaResponse)
@router.put("/llm-quota", response_model=LLMQuotaResponse, include_in_schema=False)
async def update_llm_quota(
    body: LLMQuotaConfigUpdate,
    admin_user: AuthenticatedUser = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update configured reference quota limits for active model with validation (administrators only)."""
    return await update_quota_config(db, body)


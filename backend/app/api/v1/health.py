"""Health and Readiness Probes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_storage_service
from app.core.config import settings
from app.services.ingestion.embedder import get_embedder
from app.services.storage.base import StorageService

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness():
    """Basic liveness check."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.effective_env,
    }


@router.get("/ready")
async def readiness(
    response: Response,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Readiness probe checking database connectivity, pgvector extension, and storage backend."""
    checks: dict[str, str] = {
        "database": "unknown",
        "pgvector": "unknown",
        "storage": "unknown",
        "embedding_model": "unknown",
    }

    # 1. Database connectivity
    try:
        await db.execute(text("SELECT 1;"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"unhealthy: {e!s}"

    # 2. pgvector extension check
    try:
        if settings.is_sqlite:
            checks["pgvector"] = "sqlite_dev_mode"
        else:
            ext_check = await db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector';"))
            ext_ver = ext_check.scalar()
            if ext_ver:
                checks["pgvector"] = f"ready (v{ext_ver})"
            else:
                checks["pgvector"] = "unhealthy: extension not installed"
    except Exception as e:
        checks["pgvector"] = f"error: {e!s}"

    # 3. Storage backend probe
    try:
        storage_ready = await storage.check_readiness()
        if storage_ready:
            checks["storage"] = f"ready ({settings.STORAGE_PROVIDER})"
        else:
            checks["storage"] = "unhealthy: storage access check failed"
    except Exception:
        checks["storage"] = "unhealthy: storage access check failed"

    # 4. Embedding model probe
    try:
        embedder = get_embedder()
        checks["embedding_model"] = f"loaded ({embedder.model_name})"
    except Exception as e:
        checks["embedding_model"] = f"error: {e!s}"

    is_ready = all("unhealthy" not in v and "error" not in v for v in checks.values())

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "degraded",
        "environment": settings.effective_env,
        "checks": checks,
    }

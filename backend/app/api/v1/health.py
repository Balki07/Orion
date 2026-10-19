"""Health and Readiness Probes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_storage_service
from app.core.config import settings
from app.services.ingestion.embedder import get_embedder

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness():
    """Basic liveness check."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ORION_ENV,
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe checking database connectivity and core services."""
    checks = {
        "database": "unknown",
        "embedding_model": "unknown",
        "storage": "unknown",
    }

    # 1. Database check
    try:
        await db.execute(text("SELECT 1;"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"unhealthy: {e!s}"

    # 2. Embedding model check
    try:
        embedder = get_embedder()
        checks["embedding_model"] = f"loaded ({embedder.model_name})"
    except Exception as e:
        checks["embedding_model"] = f"error: {e!s}"

    # 3. Storage check
    try:
        get_storage_service()
        checks["storage"] = f"ready ({settings.STORAGE_PROVIDER})"
    except Exception as e:
        checks["storage"] = f"error: {e!s}"

    is_ready = all("unhealthy" not in v and "error" not in v for v in checks.values())

    return {
        "status": "ready" if is_ready else "degraded",
        "checks": checks,
    }

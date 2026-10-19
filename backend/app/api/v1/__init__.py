"""API v1 Router aggregation."""

from fastapi import APIRouter

from app.api.v1.collections import router as collections_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.notes import router as notes_router
from app.api.v1.research import router as research_router
from app.api.v1.settings import router as settings_router

api_router = APIRouter()

api_router.include_router(documents_router)
api_router.include_router(collections_router)
api_router.include_router(research_router)
api_router.include_router(notes_router)
api_router.include_router(settings_router)

__all__ = ["api_router", "health_router"]

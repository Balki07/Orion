"""FastAPI Dependency Injection helpers."""

from app.db.session import get_db
from app.security.auth import AuthenticatedUser, get_current_user
from app.services.citations.validator import CitationValidator, get_citation_validator
from app.services.generation.llm import GeminiService, get_gemini_service
from app.services.ingestion.pipeline import IngestionPipeline, get_ingestion_pipeline
from app.services.retrieval.engine import RetrievalEngine, get_retrieval_engine
from app.services.storage import StorageService, get_storage_service

__all__ = [
    "AuthenticatedUser",
    "CitationValidator",
    "GeminiService",
    "IngestionPipeline",
    "RetrievalEngine",
    "StorageService",
    "get_citation_validator",
    "get_current_user",
    "get_db",
    "get_gemini_service",
    "get_ingestion_pipeline",
    "get_retrieval_engine",
    "get_storage_service",
]

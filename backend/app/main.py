"""ORION FastAPI Application Entry Point."""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router, health_router
from app.core.config import settings
from app.core.errors import OrionException
from app.core.logging import logger
from app.db.session import init_db
from app.services.ingestion.worker import ingestion_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing startup and shutdown tasks."""
    # Fail fast if production security configuration is invalid or uses dev defaults
    settings.validate_production_requirements()

    logger.info(f"Initializing {settings.APP_NAME} v{settings.APP_VERSION} [{settings.effective_env}]...")
    if settings.GEMINI_API_KEY:
        logger.info(f"Gemini key: present (length={len(settings.GEMINI_API_KEY)})")
    else:
        logger.warning("Gemini key: absent")
    await init_db()

    # Start durable background ingestion worker
    worker_task = ingestion_worker.start()

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")
    ingestion_worker.stop()
    try:
        await asyncio.wait_for(worker_task, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
        pass


app = FastAPI(
    title="ORION — AI Research Assistant API",
    description="Production-Grade AI Research Assistant with Evidence-Grounded RAG and Page-Level Citations.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms", "Retry-After", "X-CSRF-Token"],
)


# Security Headers Middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if "X-Frame-Options" not in response.headers:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.effective_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Request ID correlation & Timing Middleware
@app.middleware("http")
async def request_correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


# Global Orion Exception Handler
@app.exception_handler(OrionException)
async def orion_exception_handler(request: Request, exc: OrionException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "detail": exc.detail,
            "meta": exc.meta,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Request Validation Exception Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "detail": "Request payload validation failed.",
            "errors": jsonable_encoder(exc.errors()),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Generic Fallback Exception Handler (prevents stack trace leakage in production)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception: {exc}", exc_info=True)
    detail = str(exc) if settings.DEBUG or settings.ORION_ENV == "development" else "An unexpected internal server error occurred."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "detail": detail,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Mount Routers
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.effective_port,
        reload=settings.DEBUG,
    )

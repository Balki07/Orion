"""ORION Database Session Management, Engine Initialization, and Alembic Head Verification."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base

# Engine configuration
connect_args = {}
if settings.is_sqlite:
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

EXPECTED_ALEMBIC_HEAD = "0003_auth_audit_events"
EXPECTED_ALEMBIC_HEADS = ("0003_auth_audit_events", "0004_access_control")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding database sessions with tuned HNSW search parameters."""
    async with AsyncSessionLocal() as session:
        try:
            # Tune PostgreSQL HNSW search parameter per-session if on PostgreSQL
            if not settings.is_sqlite:
                try:
                    await session.execute(text(f"SET hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)};"))
                except Exception as ef_err:
                    logger.debug(f"Could not set hnsw.ef_search: {ef_err}")

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def verify_alembic_head(session: AsyncSession) -> None:
    """Verify that the database migration matches the expected Alembic head."""
    if settings.is_sqlite:
        return

    try:
        res = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1;"))
        current_rev = res.scalar()
        if current_rev not in EXPECTED_ALEMBIC_HEADS:
            msg = (
                f"Alembic schema mismatch: database is at revision '{current_rev}', "
                f"expected head in {EXPECTED_ALEMBIC_HEADS}. Automatic upgrades at startup are disabled for safety."
            )
            if settings.effective_env == "production":
                logger.error(f"FATAL: {msg}")
                raise RuntimeError(msg)
            else:
                logger.warning(msg)
        else:
            logger.info(f"Verified Alembic database revision matches expected head: {current_rev}")
    except Exception as e:
        if settings.effective_env == "production":
            logger.error(f"Could not verify Alembic head: {e}")
            raise
        logger.warning(f"Alembic head check skipped: {e}")


async def init_db() -> None:
    """Initialize database extensions and schema tables."""
    # Ensure all models are imported and registered on Base.metadata
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        if settings.is_sqlite:
            # In SQLite development / testing mode, create missing tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("SQLite database tables initialized successfully.")
        else:
            # In PostgreSQL mode, verify pgvector extension without modifying schema
            try:
                ext_check = await conn.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
                )
                ext_ver = ext_check.scalar()
                if ext_ver:
                    logger.info(f"Verified pgvector extension active in PostgreSQL (v{ext_ver}).")
                else:
                    logger.warning("pgvector extension not detected in pg_extension.")
            except Exception as e:
                logger.warning(f"Could not query pgvector extension: {e}")

    # Check Alembic revision in PostgreSQL
    if not settings.is_sqlite:
        async with AsyncSessionLocal() as session:
            await verify_alembic_head(session)

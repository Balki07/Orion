"""Durable Background Ingestion Worker backed by PostgreSQL / SQLite."""

import asyncio
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import IngestionError
from app.core.logging import logger
from app.db.session import AsyncSessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.ingestion.pipeline import IngestionPipeline


class DurableIngestionWorker:
    """Lightweight durable job worker recovering and processing queued document ingestion jobs.

    Backed directly by the documents table without requiring external queue infrastructure.
    """

    def __init__(self):
        self._stopped = False
        self._wake_event = asyncio.Event()
        self._pipeline: IngestionPipeline | None = None
        self._worker_task: asyncio.Task | None = None
        self._last_watchdog_check: float = 0.0

    def trigger(self):
        """Signal the worker that a new job was enqueued."""
        self._wake_event.set()

    async def recover_interrupted_jobs(self, session: AsyncSession) -> int:
        """On startup, recover jobs that were left in 'processing' or interim states during a restart."""
        interim_states = ["processing", "validating", "extracting", "chunking", "embedding", "indexing"]
        stmt = select(Document).where(Document.status.in_(interim_states))
        res = await session.execute(stmt)
        interrupted_docs = res.scalars().all()

        recovered_count = 0
        for doc in interrupted_docs:
            # Delete any partial chunks from the interrupted attempt to prevent duplicates
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))

            # Verify document owner is authorized before recovering
            owner = (await session.execute(select(User).where(User.id == doc.owner_id))).scalar_one_or_none()
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
            admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
            is_admin_owner = (
                owner is not None
                and (
                    getattr(owner, "role", None) == "admin"
                    or (owner.email and owner.email.strip().lower() in admin_emails)
                    or (owner.id and owner.id.strip() in admin_ids)
                )
            )
            if (
                not owner
                or not owner.is_active
                or owner.status != "active"
                or (not is_admin_owner and getattr(owner, "access_status", None) != "active")
            ):
                doc.status = "failed"
                doc.processing_error = "Ingestion aborted: Document owner access is restricted or disabled."
                continue

            # Inspect retry attempts safely from extraction_warnings metadata
            warnings_meta = doc.extraction_warnings or []
            retry_count = 0
            if isinstance(warnings_meta, dict):
                retry_count = warnings_meta.get("retry_count", 0)
            elif isinstance(warnings_meta, list):
                # Search for retry marker
                for item in warnings_meta:
                    if isinstance(item, str) and item.startswith("retry_count="):
                        try:
                            retry_count = int(item.split("=")[1])
                        except Exception:
                            pass

            if retry_count < settings.INGESTION_MAX_RETRIES:
                retry_count += 1
                doc.status = "queued"
                doc.processing_error = f"Recovered after server restart (attempt {retry_count}/{settings.INGESTION_MAX_RETRIES})."
                new_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("retry_count="))]
                new_warnings.append(f"retry_count={retry_count}")
                doc.extraction_warnings = new_warnings
                logger.warning(
                    f"Recovered interrupted ingestion job {doc.id} ('{doc.filename}') -> reset to 'queued' (attempt {retry_count})"
                )
                recovered_count += 1
            else:
                doc.status = "failed"
                doc.processing_error = f"Ingestion failed: exceeded maximum recovery attempts ({settings.INGESTION_MAX_RETRIES}) after restarts."
                new_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("error_code="))]
                new_warnings.append("error_code=ERR_INGESTION_MAX_RETRIES")
                doc.extraction_warnings = new_warnings
                logger.error(
                    f"Interrupted ingestion job {doc.id} ('{doc.filename}') exceeded max retries -> marked as 'failed'"
                )

        if interrupted_docs:
            await session.commit()
        return recovered_count

    async def recover_stuck_jobs(self, session: AsyncSession) -> int:
        """Watchdog: Detect and recover jobs in active ingestion states beyond timeout."""
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.INGESTION_STUCK_TIMEOUT_SECONDS)
        interim_states = ["processing", "validating", "extracting", "chunking", "embedding", "indexing"]

        stmt = select(Document).where(
            Document.status.in_(interim_states),
            Document.updated_at < cutoff,
        )
        if not settings.is_sqlite:
            stmt = stmt.with_for_update(skip_locked=True)

        res = await session.execute(stmt)
        stuck_docs = res.scalars().all()

        recovered_count = 0
        for doc in stuck_docs:
            # Delete any partial chunks from the stuck run to prevent duplicates
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))

            # Verify document owner is authorized before recovering
            owner = (await session.execute(select(User).where(User.id == doc.owner_id))).scalar_one_or_none()
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
            admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
            is_admin_owner = (
                owner is not None
                and (
                    getattr(owner, "role", None) == "admin"
                    or (owner.email and owner.email.strip().lower() in admin_emails)
                    or (owner.id and owner.id.strip() in admin_ids)
                )
            )
            if (
                not owner
                or not owner.is_active
                or owner.status != "active"
                or (not is_admin_owner and getattr(owner, "access_status", None) != "active")
            ):
                doc.status = "failed"
                doc.processing_error = "Ingestion aborted: Document owner access is restricted or disabled."
                continue

            warnings_meta = doc.extraction_warnings or []
            retry_count = 0
            if isinstance(warnings_meta, dict):
                retry_count = warnings_meta.get("retry_count", 0)
            elif isinstance(warnings_meta, list):
                for item in warnings_meta:
                    if isinstance(item, str) and item.startswith("retry_count="):
                        try:
                            retry_count = int(item.split("=")[1])
                        except Exception:
                            pass

            if retry_count < settings.INGESTION_MAX_RETRIES:
                retry_count += 1
                doc.status = "queued"
                doc.processing_error = (
                    f"Ingestion timed out after {settings.INGESTION_STUCK_TIMEOUT_SECONDS}s; "
                    f"re-queued by watchdog (attempt {retry_count}/{settings.INGESTION_MAX_RETRIES})."
                )
                new_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("retry_count="))]
                new_warnings.append(f"retry_count={retry_count}")
                doc.extraction_warnings = new_warnings
                logger.warning(
                    f"Watchdog recovered stuck ingestion job {doc.id} ('{doc.filename}') from state '{doc.status}' -> reset to 'queued' (attempt {retry_count})"
                )
                recovered_count += 1
            else:
                doc.status = "failed"
                doc.processing_error = (
                    f"Ingestion timed out after {settings.INGESTION_STUCK_TIMEOUT_SECONDS}s and exceeded "
                    f"maximum recovery attempts ({settings.INGESTION_MAX_RETRIES})."
                )
                new_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("error_code="))]
                new_warnings.append("error_code=ERR_INGESTION_TIMEOUT")
                doc.extraction_warnings = new_warnings
                logger.error(
                    f"Watchdog marked stuck job {doc.id} ('{doc.filename}') as permanently 'failed' after {retry_count} attempts."
                )

        if stuck_docs:
            await session.commit()
            if recovered_count > 0:
                self.trigger()

        return len(stuck_docs)

    async def process_next_job(self) -> bool:
        """Fetch and process the oldest queued document atomically."""
        async with AsyncSessionLocal() as session:
            # 1. Acquire oldest queued document
            stmt = select(Document).where(Document.status == "queued").order_by(Document.created_at.asc()).limit(1)

            # In PostgreSQL, use FOR UPDATE SKIP LOCKED to prevent concurrent worker duplication
            if not settings.is_sqlite:
                stmt = stmt.with_for_update(skip_locked=True)

            res = await session.execute(stmt)
            doc = res.scalar_one_or_none()

            if not doc:
                return False

            # Verify document owner authorization before proceeding
            owner = (await session.execute(select(User).where(User.id == doc.owner_id))).scalar_one_or_none()
            admin_emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
            admin_ids = [uid.strip() for uid in settings.ADMIN_USER_IDS if uid.strip()]
            is_admin_owner = (
                owner is not None
                and (
                    getattr(owner, "role", None) == "admin"
                    or (owner.email and owner.email.strip().lower() in admin_emails)
                    or (owner.id and owner.id.strip() in admin_ids)
                )
            )

            if not owner or not owner.is_active or owner.status != "active":
                doc.status = "failed"
                doc.processing_error = "Ingestion aborted: Document owner account is inactive or disabled."
                await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await session.commit()
                logger.warning(f"Aborted ingestion for doc {doc.id}: owner {doc.owner_id} account inactive/disabled.")
                return True

            if not is_admin_owner and getattr(owner, "access_status", None) != "active":
                doc.status = "failed"
                doc.processing_error = f"Ingestion aborted: Document owner research access is restricted ({owner.access_status})."
                await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await session.commit()
                logger.warning(f"Aborted ingestion for doc {doc.id}: owner {doc.owner_id} access_status is '{owner.access_status}'.")
                return True

            doc_id = doc.id
            filename = doc.filename

            # Mark as processing atomically
            doc.status = "processing"
            doc.processing_error = None
            await session.commit()

        # 2. Execute ingestion pipeline in separate session
        if not self._pipeline:
            self._pipeline = IngestionPipeline()

        async with AsyncSessionLocal() as session:
            try:
                await self._pipeline.process_document(doc_id, session)
                logger.info(f"Durable worker successfully finished ingestion for {doc_id} ('{filename}')")
                return True
            except Exception as exc:
                logger.error(f"Durable worker encountered error for {doc_id} ('{filename}'): {exc}", exc_info=True)
                # Retry evaluation
                async with AsyncSessionLocal() as err_session:
                    doc_check = (await err_session.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
                    if doc_check:
                        # Check if error is permanent (e.g. invalid, password-protected, or scanned PDF)
                        is_permanent = False
                        if isinstance(exc, IngestionError) and exc.error_code in (
                            "ERR_PDF_ENCRYPTED",
                            "ERR_PDF_SCANNED_NO_TEXT",
                            "ERR_PDF_CORRUPT",
                            "ERR_PDF_EMPTY",
                            "ERR_PDF_PAGE_LIMIT",
                        ):
                            is_permanent = True

                        warnings_meta = doc_check.extraction_warnings or []
                        retry_count = 0
                        for item in warnings_meta:
                            if isinstance(item, str) and item.startswith("retry_count="):
                                try:
                                    retry_count = int(item.split("=")[1])
                                except Exception:
                                    pass

                        if not is_permanent and retry_count < settings.INGESTION_MAX_RETRIES:
                            retry_count += 1
                            doc_check.status = "queued"
                            doc_check.processing_error = f"Transient failure on attempt {retry_count}: {getattr(exc, 'detail', str(exc))}"
                            new_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("retry_count="))]
                            new_warnings.append(f"retry_count={retry_count}")
                            doc_check.extraction_warnings = new_warnings
                            logger.info(f"Re-queued document {doc_id} for retry attempt {retry_count}")
                        else:
                            doc_check.status = "failed"
                            if is_permanent:
                                doc_check.processing_error = getattr(exc, "detail", str(exc))
                            else:
                                doc_check.processing_error = f"Ingestion failed after {retry_count} attempts: {getattr(exc, 'detail', str(exc))}"
                            logger.error(f"Document {doc_id} marked as 'failed' (permanent={is_permanent}, attempts={retry_count}).")
                        await err_session.commit()
                return True

    async def run(self):
        """Worker event loop running for the lifespan of the backend process."""
        logger.info("Starting Durable Ingestion Worker...")

        # Run startup recovery
        try:
            async with AsyncSessionLocal() as session:
                recovered = await self.recover_interrupted_jobs(session)
                if recovered:
                    logger.info(f"Durable Ingestion Worker recovered {recovered} interrupted jobs on startup.")
        except Exception as e:
            logger.error(f"Error during startup job recovery: {e}", exc_info=True)

        while not self._stopped:
            try:
                # Periodic watchdog execution for stuck in-flight jobs
                now = time.time()
                if now - self._last_watchdog_check >= settings.INGESTION_WATCHDOG_INTERVAL_SECONDS:
                    self._last_watchdog_check = now
                    try:
                        async with AsyncSessionLocal() as session:
                            stuck = await self.recover_stuck_jobs(session)
                            if stuck > 0:
                                logger.warning(f"Ingestion watchdog reclaimed {stuck} stuck job(s).")
                    except Exception as wex:
                        logger.error(f"Error during watchdog execution: {wex}", exc_info=True)

                has_work = await self.process_next_job()
                if not has_work:
                    # Wait for either a trigger signal or polling timeout
                    try:
                        await asyncio.wait_for(
                            self._wake_event.wait(),
                            timeout=settings.INGESTION_WORKER_POLL_INTERVAL_SECONDS,
                        )
                        self._wake_event.clear()
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unhandled error in Durable Ingestion Worker loop: {e}", exc_info=True)
                await asyncio.sleep(2.0)

        logger.info("Durable Ingestion Worker stopped.")

    def start(self) -> asyncio.Task:
        if not self._worker_task or self._worker_task.done():
            self._stopped = False
            self._worker_task = asyncio.create_task(self.run())
        return self._worker_task

    def stop(self):
        self._stopped = True
        self._wake_event.set()
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()


# Singleton instance
ingestion_worker = DurableIngestionWorker()


def get_ingestion_worker() -> DurableIngestionWorker:
    return ingestion_worker


if __name__ == "__main__":
    from app.db.session import init_db

    async def main():
        logger.info("Initializing database connectivity for standalone ingestion worker...")
        await init_db()
        await ingestion_worker.run()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Ingestion worker interrupted by user. Exiting cleanly.")


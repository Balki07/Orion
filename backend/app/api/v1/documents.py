"""Documents management and ingestion REST API."""

import asyncio
import hashlib
import pymupdf

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedUser,
    StorageService,
    get_db,
    get_ingestion_pipeline,
    get_storage_service,
    require_active_researcher,
)
from app.core.config import settings
from app.core.errors import (
    DocumentNotFoundError,
    FileValidationError,
    OrionException,
    StorageQuotaExceededError,
)
from app.core.logging import logger
from app.db.base import generate_uuid
from app.db.session import AsyncSessionLocal
from app.models.chunk import Chunk
from app.models.collection import DocumentCollection
from app.models.document import Document
from app.models.user import User
from app.schemas.document import (
    BatchItemResult,
    DocumentBatchResponse,
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    DocumentStatusResponse,
    StorageUsageResponse,
)
from app.security.permissions import verify_ownership
from app.services.ingestion.worker import get_ingestion_worker

router = APIRouter(prefix="/documents", tags=["Documents"])

_user_upload_locks: dict[str, asyncio.Lock] = {}
_upload_locks_mutex = asyncio.Lock()


async def get_user_upload_lock(user_id: str) -> asyncio.Lock:
    """Retrieve or create an asyncio.Lock per user to serialize concurrent uploads within process."""
    async with _upload_locks_mutex:
        if user_id not in _user_upload_locks:
            _user_upload_locks[user_id] = asyncio.Lock()
        return _user_upload_locks[user_id]


async def get_user_storage_usage(user_id: str, db: AsyncSession) -> tuple[int, int]:
    """Calculate cumulative stored bytes and document count for user.
    Excludes documents in 'failed' status whose storage assets are purged.
    """
    stmt = select(
        func.coalesce(func.sum(Document.file_size), 0),
        func.count(Document.id),
    ).where(
        Document.owner_id == user_id,
        Document.status != "failed",
    )
    result = await db.execute(stmt)
    used_bytes, count = result.one()
    return int(used_bytes), int(count)


async def run_background_ingestion(document_id: str):
    """Backward compatibility hook for test mocking; forwards dispatch to DurableIngestionWorker."""
    get_ingestion_worker().trigger()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_id: str | None = Query(None),
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Upload a research PDF for validation, storage, and asynchronous ingestion."""
    # 1. Validate file extension
    filename = file.filename or "uploaded_paper.pdf"
    if not filename.lower().endswith(".pdf"):
        raise FileValidationError("Only PDF documents (.pdf) are supported in this release.")

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise FileValidationError("Uploaded file is empty (0 bytes).")

    if file_size > settings.max_upload_size_bytes:
        raise FileValidationError(
            f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # Validate PDF signature magic bytes: %PDF-
    if not content.startswith(b"%PDF-"):
        raise FileValidationError("File content does not match standard PDF header signature (%PDF-).")

    content_hash = hashlib.sha256(content).hexdigest()

    # 2. Duplicate detection for this user
    dup_stmt = select(Document).where(
        Document.owner_id == current_user.id,
        Document.content_hash == content_hash,
    )
    dup_res = await db.execute(dup_stmt)
    existing_doc = dup_res.scalar_one_or_none()
    if existing_doc and existing_doc.status == "completed":
        # Return existing document (consumes no additional storage)
        c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == existing_doc.id)
        c_res = await db.execute(c_count_stmt)
        c_count = c_res.scalar() or 0
        resp = DocumentResponse.model_validate(existing_doc)
        resp.chunk_count = c_count
        return resp

    # Concurrency and Quota Guard
    user_lock = await get_user_upload_lock(current_user.id)
    async with user_lock:
        if not settings.is_sqlite:
            # Row-level lock across multiple instances in PostgreSQL
            await db.execute(select(User.id).where(User.id == current_user.id).with_for_update())

        # Check per-user document cap
        user_count_stmt = select(func.count(Document.id)).where(Document.owner_id == current_user.id)
        user_count_res = await db.execute(user_count_stmt)
        current_count = user_count_res.scalar() or 0
        if current_count >= settings.USER_DOCUMENT_LIMIT:
            raise FileValidationError(
                f"Per-user document limit reached ({settings.USER_DOCUMENT_LIMIT} max). Please delete older documents before uploading."
            )

        # Check per-user cumulative storage quota (500 MB default)
        used_bytes, _ = await get_user_storage_usage(current_user.id, db)
        quota_bytes = settings.user_storage_quota_bytes
        if used_bytes + file_size > quota_bytes:
            remaining_bytes = max(0, quota_bytes - used_bytes)
            used_mb = used_bytes / (1024 * 1024)
            quota_mb = settings.USER_STORAGE_QUOTA_MB
            remaining_mb = remaining_bytes / (1024 * 1024)
            req_mb = file_size / (1024 * 1024)
            raise StorageQuotaExceededError(
                detail=(
                    f"Storage quota exceeded. Current usage: {used_mb:.2f} MB of {quota_mb} MB limit "
                    f"({remaining_mb:.2f} MB remaining). Cannot accept file '{filename}' of size {req_mb:.2f} MB."
                ),
                current_bytes=used_bytes,
                quota_bytes=quota_bytes,
                remaining_bytes=remaining_bytes,
                requested_bytes=file_size,
            )

        # 3. Save to storage engine with unique storage key
        doc_id = generate_uuid("doc")
        storage_key = f"{current_user.id}/{doc_id}/{filename}"
        await storage.save_file(content, storage_key)

        # 4. Create document record
        doc = Document(
            id=doc_id,
            owner_id=current_user.id,
            filename=filename,
            storage_key=storage_key,
            content_hash=content_hash,
            file_size=file_size,
            status="queued",
        )
        db.add(doc)
        await db.flush()

        if collection_id:
            doc_coll = DocumentCollection(document_id=doc.id, collection_id=collection_id)
            db.add(doc_coll)

        await db.commit()
        await db.refresh(doc)

    # 5. Trigger durable background ingestion worker (single authoritative engine)
    get_ingestion_worker().trigger()

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = 0
    return resp


@router.post("/batch", status_code=status.HTTP_201_CREATED, response_model=DocumentBatchResponse)
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    collection_id: str | None = Query(None),
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Upload multiple research PDFs in one batch for validation, storage, and asynchronous ingestion."""
    if not files:
        raise FileValidationError("At least one PDF file must be provided in the batch.")

    if len(files) > settings.MAX_BATCH_FILES:
        raise FileValidationError(
            f"Batch contains {len(files)} files, which exceeds the limit of {settings.MAX_BATCH_FILES} files."
        )

    results: list[BatchItemResult] = []
    total_batch_bytes = 0
    batch_accepted_bytes = 0
    accepted_docs_count = 0

    user_lock = await get_user_upload_lock(current_user.id)
    async with user_lock:
        if not settings.is_sqlite:
            await db.execute(select(User.id).where(User.id == current_user.id).with_for_update())

        user_count_stmt = select(func.count(Document.id)).where(Document.owner_id == current_user.id)
        user_count_res = await db.execute(user_count_stmt)
        current_doc_count = user_count_res.scalar() or 0

        # Current cumulative stored bytes
        used_bytes, _ = await get_user_storage_usage(current_user.id, db)
        quota_bytes = settings.user_storage_quota_bytes

        for file in files:
            filename = file.filename or "uploaded_paper.pdf"

            # Check per-user document cap
            if current_doc_count + accepted_docs_count >= settings.USER_DOCUMENT_LIMIT:
                results.append(
                    BatchItemResult(
                        filename=filename,
                        file_size=0,
                        status="rejected",
                        error=f"Per-user document limit reached ({settings.USER_DOCUMENT_LIMIT} max).",
                    )
                )
                continue

            # 1. Validate file extension
            if not filename.lower().endswith(".pdf"):
                results.append(
                    BatchItemResult(
                        filename=filename,
                        file_size=0,
                        status="rejected",
                        error="Only PDF documents (.pdf) are supported in this release.",
                    )
                )
                continue

            try:
                content = await file.read()
                file_size = len(content)
                total_batch_bytes += file_size

                # Check individual file size
                if file_size == 0:
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=0,
                            status="rejected",
                            error="Uploaded file is empty (0 bytes).",
                        )
                    )
                    continue

                if file_size > settings.max_upload_size_bytes:
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=file_size,
                            status="rejected",
                            error=f"File size exceeds the limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                        )
                    )
                    continue

                # Check batch size limit
                if total_batch_bytes > settings.max_batch_size_bytes:
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=file_size,
                            status="rejected",
                            error=f"Batch size exceeds total limit of {settings.MAX_BATCH_SIZE_MB}MB.",
                        )
                    )
                    continue

                # Validate PDF signature magic bytes: %PDF-
                if not content.startswith(b"%PDF-"):
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=file_size,
                            status="rejected",
                            error="File content does not match standard PDF header signature (%PDF-).",
                        )
                    )
                    continue

                content_hash = hashlib.sha256(content).hexdigest()

                # Duplicate detection for this user
                dup_stmt = select(Document).where(
                    Document.owner_id == current_user.id,
                    Document.content_hash == content_hash,
                )
                dup_res = await db.execute(dup_stmt)
                existing_doc = dup_res.scalar_one_or_none()
                if existing_doc and existing_doc.status == "completed":
                    c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == existing_doc.id)
                    c_res = await db.execute(c_count_stmt)
                    c_count = c_res.scalar() or 0
                    resp = DocumentResponse.model_validate(existing_doc)
                    resp.chunk_count = c_count
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=file_size,
                            status="completed",
                            document=resp,
                        )
                    )
                    continue

                # Check cumulative quota for this user
                if used_bytes + batch_accepted_bytes + file_size > quota_bytes:
                    remaining_bytes = max(0, quota_bytes - (used_bytes + batch_accepted_bytes))
                    used_mb = (used_bytes + batch_accepted_bytes) / (1024 * 1024)
                    quota_mb = settings.USER_STORAGE_QUOTA_MB
                    remaining_mb = remaining_bytes / (1024 * 1024)
                    req_mb = file_size / (1024 * 1024)
                    results.append(
                        BatchItemResult(
                            filename=filename,
                            file_size=file_size,
                            status="rejected",
                            error=(
                                f"Storage quota exceeded. Current usage: {used_mb:.2f} MB of {quota_mb} MB limit "
                                f"({remaining_mb:.2f} MB remaining). Cannot accept file '{filename}' of size {req_mb:.2f} MB."
                            ),
                        )
                    )
                    continue

                # Save to storage engine with unique storage key
                doc_id = generate_uuid("doc")
                storage_key = f"{current_user.id}/{doc_id}/{filename}"
                await storage.save_file(content, storage_key)

                # Create document record
                doc = Document(
                    id=doc_id,
                    owner_id=current_user.id,
                    filename=filename,
                    storage_key=storage_key,
                    content_hash=content_hash,
                    file_size=file_size,
                    status="queued",
                )
                db.add(doc)
                await db.flush()

                if collection_id:
                    doc_coll = DocumentCollection(document_id=doc.id, collection_id=collection_id)
                    db.add(doc_coll)

                await db.commit()
                await db.refresh(doc)
                accepted_docs_count += 1
                batch_accepted_bytes += file_size

                # Trigger durable background ingestion worker (single authoritative engine)
                get_ingestion_worker().trigger()

                resp = DocumentResponse.model_validate(doc)
                resp.chunk_count = 0
                results.append(
                    BatchItemResult(
                        filename=filename,
                        file_size=file_size,
                        status="queued",
                        document=resp,
                    )
                )

            except Exception as exc:
                logger.error(f"Failed to process file '{filename}' in batch: {exc}", exc_info=True)
                results.append(
                    BatchItemResult(
                        filename=filename,
                        file_size=0,
                        status="rejected",
                        error=f"Processing error: {exc!s}",
                    )
                )

    successful_count = sum(1 for r in results if r.status in ("queued", "completed"))
    failed_count = sum(1 for r in results if r.status == "rejected")

    return DocumentBatchResponse(
        total=len(files),
        successful_count=successful_count,
        failed_count=failed_count,
        items=results,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """List documents owned by authenticated user with pagination, search, and filtering."""
    stmt = select(Document).where(Document.owner_id == current_user.id)

    if collection_id:
        stmt = stmt.join(DocumentCollection, Document.id == DocumentCollection.document_id).where(
            DocumentCollection.collection_id == collection_id
        )

    if status_filter:
        stmt = stmt.where(Document.status == status_filter)

    if search:
        stmt = stmt.where(Document.filename.ilike(f"%{search}%"))

    # Total count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    # Paged query
    stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    documents = res.scalars().all()

    # Hydrate chunk counts
    doc_ids = [d.id for d in documents]
    chunk_counts = {}
    if doc_ids:
        cc_stmt = select(Chunk.document_id, func.count(Chunk.id)).where(Chunk.document_id.in_(doc_ids)).group_by(Chunk.document_id)
        cc_res = await db.execute(cc_stmt)
        for did, count in cc_res.all():
            chunk_counts[did] = count

    items = []
    for d in documents:
        item = DocumentResponse.model_validate(d)
        item.chunk_count = chunk_counts.get(d.id, 0)
        items.append(item)

    return DocumentListResponse(total=total, items=items)


@router.get("/storage-usage", response_model=StorageUsageResponse)
async def get_storage_usage(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve cumulative storage consumption and quota statistics for the current user."""
    used_bytes, doc_count = await get_user_storage_usage(current_user.id, db)
    total_quota_bytes = settings.user_storage_quota_bytes
    remaining_bytes = max(0, total_quota_bytes - used_bytes)
    usage_pct = round((used_bytes / total_quota_bytes) * 100, 4) if total_quota_bytes > 0 else 0.0

    return StorageUsageResponse(
        total_quota_bytes=total_quota_bytes,
        used_storage_bytes=used_bytes,
        remaining_storage_bytes=remaining_bytes,
        usage_percentage=min(100.0, usage_pct),
        document_count=doc_count,
        quota_mb=settings.USER_STORAGE_QUOTA_MB,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve metadata for a specific document."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
    c_res = await db.execute(c_count_stmt)
    c_count = c_res.scalar() or 0

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = c_count
    return resp


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Poll ingestion status and progress for a document."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    progress_map = {
        "queued": 15,
        "uploaded": 15,
        "processing": 50,
        "validating": 25,
        "extracting": 45,
        "chunking": 65,
        "embedding": 85,
        "indexing": 95,
        "ready": 100,
        "completed": 100,
        "failed": 0,
    }

    c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
    c_res = await db.execute(c_count_stmt)
    c_count = c_res.scalar() or 0

    error_code = None
    if doc.extraction_warnings:
        for w in doc.extraction_warnings:
            if isinstance(w, str) and w.startswith("error_code="):
                error_code = w.split("=", 1)[1]
                break

    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        progress_percentage=progress_map.get(doc.status, 0),
        page_count=doc.page_count,
        chunk_count=c_count,
        error=doc.processing_error,
        error_code=error_code,
        warnings=doc.extraction_warnings or [],
    )


@router.get("/{document_id}/pages/{page_number}", response_model=DocumentPageResponse)
async def get_document_page(
    document_id: str,
    page_number: int,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Fetch text from a specific page of the original PDF."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    pdf_bytes = await storage.read_file(doc.storage_key)
    pipeline = get_ingestion_pipeline()
    extraction = pipeline.extractor.extract_from_bytes(pdf_bytes, filename=doc.filename)

    matching_pages = [p for p in extraction.pages if p.page_number == page_number]
    if not matching_pages:
        raise FileValidationError(f"Page {page_number} not found in document.")

    target_page = matching_pages[0]
    return DocumentPageResponse(
        document_id=doc.id,
        page_number=page_number,
        text=target_page.text,
        character_count=target_page.character_count,
        word_count=len(target_page.text.split()),
        has_text=target_page.has_text,
    )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Serve the raw PDF file binary for evidence inspection and page navigation."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    pdf_bytes = await storage.read_file(doc.storage_key)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc.filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{document_id}/pages/{page_number}/render")
async def render_document_page(
    document_id: str,
    page_number: int,
    dpi: int = Query(150, ge=72, le=300),
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Render a specific PDF page to a crisp PNG image using PyMuPDF."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    # Check cached rendered page in storage backend
    render_key = f"{doc.owner_id}/{doc.id}/renders/page_{page_number}_dpi{dpi}.png"
    if await storage.exists(render_key):
        try:
            cached_img = await storage.open(render_key)
            return Response(
                content=cached_img,
                media_type="image/png",
                headers={"Cache-Control": "private, max-age=3600"},
            )
        except Exception:
            pass

    pdf_bytes = await storage.read_file(doc.storage_key)
    try:
        pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise FileValidationError(f"Could not parse PDF for page rendering: {e}")

    total_pages = len(pdf_doc)
    if page_number < 1 or page_number > total_pages:
        pdf_doc.close()
        raise FileValidationError(f"Page {page_number} is out of bounds (1-{total_pages}).")

    try:
        page = pdf_doc[page_number - 1]
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        pdf_doc.close()
    except Exception as e:
        pdf_doc.close()
        raise FileValidationError(f"Failed to render page {page_number}: {e}")

    # Cache rendered page image in storage backend
    try:
        await storage.save(render_key, img_bytes, content_type="image/png")
    except Exception as cache_err:
        logger.debug(f"Could not cache page render to storage: {cache_err}")

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/{document_id}/retry", response_model=DocumentResponse)
async def retry_document_ingestion(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retry an ingestion job that encountered a transient failure."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    # Reject retrying if the document is actively being processed by a worker
    if doc.status in ("processing", "validating", "extracting", "chunking", "embedding", "indexing"):
        raise OrionException(
            status_code=status.HTTP_409_CONFLICT,
            code="DOCUMENT_IN_PROGRESS",
            detail=f"Document is currently in-flight (status: '{doc.status}'). Cannot retry an active ingestion job.",
        )

    doc.status = "queued"
    doc.processing_error = None
    # Reset retry count marker for user-initiated manual retry
    warnings_meta = doc.extraction_warnings or []
    doc.extraction_warnings = [w for w in warnings_meta if not (isinstance(w, str) and w.startswith("retry_count="))]
    await db.commit()
    await db.refresh(doc)

    get_ingestion_worker().trigger()
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Delete a document, cascade deleting all chunks, embeddings, and raw storage files."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    # 1. Delete all raw files and cached renders under {owner_id}/{doc_id} prefix
    doc_prefix = f"{current_user.id}/{doc.id}"
    try:
        deleted_files = await storage.delete_prefix(doc_prefix)
        logger.info(f"Purged {deleted_files} storage objects for prefix '{doc_prefix}'")
    except Exception as e:
        logger.warning(f"Could not purge storage prefix '{doc_prefix}': {e}")
        try:
            await storage.delete(doc.storage_key)
        except Exception:
            pass

    # 2. Delete database record (cascade deletes chunks and collection links)
    await db.delete(doc)
    await db.commit()
    logger.info(f"Deleted document {document_id} and purged all associated chunks.")

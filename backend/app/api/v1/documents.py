"""Documents management and ingestion REST API."""

import hashlib

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedUser,
    StorageService,
    get_current_user,
    get_db,
    get_ingestion_pipeline,
    get_storage_service,
)
from app.core.config import settings
from app.core.errors import (
    DocumentNotFoundError,
    FileValidationError,
)
from app.core.logging import logger
from app.db.base import generate_uuid
from app.db.session import AsyncSessionLocal
from app.models.chunk import Chunk
from app.models.collection import DocumentCollection
from app.models.document import Document
from app.schemas.document import (
    DocumentListResponse,
    DocumentPageResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.security.permissions import verify_ownership

router = APIRouter(prefix="/documents", tags=["Documents"])


async def run_background_ingestion(document_id: str):
    """Asynchronous background task runner for document ingestion."""
    pipeline = get_ingestion_pipeline()
    async with AsyncSessionLocal() as session:
        try:
            await pipeline.process_document(document_id, session)
        except Exception as e:
            logger.error(f"Background ingestion failed for {document_id}: {e}", exc_info=True)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_id: str | None = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Upload a research PDF for validation, storage, and asynchronous ingestion."""
    # 1. Validate file extension and MIME type
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
        # Return existing document
        c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == existing_doc.id)
        c_res = await db.execute(c_count_stmt)
        c_count = c_res.scalar() or 0
        resp = DocumentResponse.model_validate(existing_doc)
        resp.chunk_count = c_count
        return resp

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
        status="uploaded",
    )
    db.add(doc)
    await db.flush()

    if collection_id:
        doc_coll = DocumentCollection(document_id=doc.id, collection_id=collection_id)
        db.add(doc_coll)

    await db.commit()
    await db.refresh(doc)

    # 5. Trigger background ingestion
    background_tasks.add_task(run_background_ingestion, doc.id)

    resp = DocumentResponse.model_validate(doc)
    resp.chunk_count = 0
    return resp


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
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


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
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
        "uploaded": 10,
        "validating": 25,
        "extracting": 45,
        "chunking": 65,
        "embedding": 85,
        "indexing": 95,
        "completed": 100,
        "failed": 0,
    }

    c_count_stmt = select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
    c_res = await db.execute(c_count_stmt)
    c_count = c_res.scalar() or 0

    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        progress_percentage=progress_map.get(doc.status, 0),
        page_count=doc.page_count,
        chunk_count=c_count,
        error=doc.processing_error,
        warnings=doc.extraction_warnings or [],
    )


@router.get("/{document_id}/pages/{page_number}", response_model=DocumentPageResponse)
async def get_document_page(
    document_id: str,
    page_number: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
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


@router.post("/{document_id}/retry", response_model=DocumentResponse)
async def retry_document_ingestion(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry an ingestion job that encountered a transient failure."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise DocumentNotFoundError(document_id)

    verify_ownership(doc.owner_id, current_user.id, "document")

    doc.status = "uploaded"
    doc.processing_error = None
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(run_background_ingestion, doc.id)
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
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

    # 1. Delete raw file from storage
    try:
        await storage.delete_file(doc.storage_key)
    except Exception as e:
        logger.warning(f"Could not delete storage key '{doc.storage_key}': {e}")

    # 2. Delete database record (cascade deletes chunks and collection links)
    await db.delete(doc)
    await db.commit()
    logger.info(f"Deleted document {document_id} and purged all associated chunks.")

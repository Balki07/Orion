"""Collections management REST API."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthenticatedUser, get_db, require_active_researcher
from app.core.errors import CollectionNotFoundError
from app.models.collection import Collection, DocumentCollection
from app.models.document import Document
from app.schemas.collection import (
    AddDocumentToCollectionRequest,
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from app.security.permissions import verify_ownership

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CollectionResponse)
async def create_collection(
    body: CollectionCreate,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Create a new research collection."""
    coll = Collection(
        owner_id=current_user.id,
        name=body.name,
        description=body.description,
    )
    db.add(coll)
    await db.commit()
    await db.refresh(coll)
    resp = CollectionResponse.model_validate(coll)
    resp.document_count = 0
    return resp


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """List all collections owned by authenticated user with member counts."""
    stmt = (
        select(Collection, func.count(DocumentCollection.id).label("doc_count"))
        .outerjoin(DocumentCollection, Collection.id == DocumentCollection.collection_id)
        .where(Collection.owner_id == current_user.id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    items = []
    for coll, count in rows:
        item = CollectionResponse.model_validate(coll)
        item.document_count = count
        items.append(item)

    return CollectionListResponse(total=len(items), items=items)


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a collection."""
    stmt = select(Collection).where(Collection.id == collection_id)
    res = await db.execute(stmt)
    coll = res.scalar_one_or_none()
    if not coll:
        raise CollectionNotFoundError(collection_id)

    verify_ownership(coll.owner_id, current_user.id, "collection")

    c_stmt = select(func.count(DocumentCollection.id)).where(DocumentCollection.collection_id == coll.id)
    c_res = await db.execute(c_stmt)
    count = c_res.scalar() or 0

    resp = CollectionResponse.model_validate(coll)
    resp.document_count = count
    return resp


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    body: CollectionUpdate,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Update name or description of a collection."""
    stmt = select(Collection).where(Collection.id == collection_id)
    res = await db.execute(stmt)
    coll = res.scalar_one_or_none()
    if not coll:
        raise CollectionNotFoundError(collection_id)

    verify_ownership(coll.owner_id, current_user.id, "collection")

    if body.name is not None:
        coll.name = body.name
    if body.description is not None:
        coll.description = body.description

    await db.commit()
    await db.refresh(coll)

    c_stmt = select(func.count(DocumentCollection.id)).where(DocumentCollection.collection_id == coll.id)
    c_res = await db.execute(c_stmt)
    count = c_res.scalar() or 0

    resp = CollectionResponse.model_validate(coll)
    resp.document_count = count
    return resp


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Delete a collection record."""
    stmt = select(Collection).where(Collection.id == collection_id)
    res = await db.execute(stmt)
    coll = res.scalar_one_or_none()
    if not coll:
        raise CollectionNotFoundError(collection_id)

    verify_ownership(coll.owner_id, current_user.id, "collection")
    await db.delete(coll)
    await db.commit()


@router.post("/{collection_id}/documents", status_code=status.HTTP_200_OK)
async def add_documents_to_collection(
    collection_id: str,
    body: AddDocumentToCollectionRequest,
    current_user: AuthenticatedUser = Depends(require_active_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Associate documents with a collection."""
    stmt = select(Collection).where(Collection.id == collection_id)
    res = await db.execute(stmt)
    coll = res.scalar_one_or_none()
    if not coll:
        raise CollectionNotFoundError(collection_id)

    verify_ownership(coll.owner_id, current_user.id, "collection")

    for did in body.document_ids:
        # Check document ownership
        d_res = await db.execute(select(Document).where(Document.id == did))
        doc = d_res.scalar_one_or_none()
        if doc and doc.owner_id == current_user.id:
            # Check not already member
            m_res = await db.execute(
                select(DocumentCollection).where(
                    DocumentCollection.document_id == did,
                    DocumentCollection.collection_id == collection_id,
                )
            )
            if not m_res.scalar_one_or_none():
                db.add(DocumentCollection(document_id=did, collection_id=collection_id))

    await db.commit()
    return {"status": "success", "collection_id": collection_id}

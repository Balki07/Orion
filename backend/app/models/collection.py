"""Collection and DocumentCollection membership models."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.document import Document


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("coll"),
    )
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list["DocumentCollection"]] = relationship(
        "DocumentCollection",
        back_populates="collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentCollection(Base):
    __tablename__ = "document_collections"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: generate_uuid("dcol"),
    )
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="collections")
    collection: Mapped["Collection"] = relationship("Collection", back_populates="documents")

    __table_args__ = (
        UniqueConstraint("document_id", "collection_id", name="uq_document_collection"),
        Index("ix_doc_coll_pair", "document_id", "collection_id"),
    )

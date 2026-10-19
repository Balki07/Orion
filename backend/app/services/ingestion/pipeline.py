"""ORION Ingestion Pipeline orchestrator."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.ingestion.chunker import PageAwareChunker
from app.services.ingestion.embedder import get_embedder
from app.services.ingestion.extractor import PdfExtractor
from app.services.storage import get_storage_service


class IngestionPipeline:
    def __init__(self):
        self.storage = get_storage_service()
        self.extractor = PdfExtractor(max_pages=settings.MAX_PDF_PAGES)
        self.chunker = PageAwareChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self.embedder = get_embedder()

    async def process_document(self, document_id: str, db: AsyncSession) -> Document:
        """Executes full ingestion pipeline asynchronously:

        storage read -> validate -> extract -> chunk -> embed -> persist -> complete.
        """
        stmt = select(Document).where(Document.id == document_id)
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found for ingestion.")

        try:
            logger.info(f"Starting ingestion for document {document_id} ('{doc.filename}')...")

            # 1. State: validating
            doc.status = "validating"
            await db.commit()

            pdf_bytes = await self.storage.read_file(doc.storage_key)
            if not pdf_bytes:
                raise ValueError("PDF content could not be read from storage.")

            # 2. State: extracting
            doc.status = "extracting"
            await db.commit()

            extraction = self.extractor.extract_from_bytes(pdf_bytes, filename=doc.filename)
            doc.page_count = extraction.total_pages
            doc.extraction_warnings = extraction.warnings
            await db.commit()

            # 3. State: chunking
            doc.status = "chunking"
            await db.commit()

            text_chunks = self.chunker.chunk_pages(extraction.pages)
            if not text_chunks and not extraction.is_scanned_or_empty:
                raise ValueError("Failed to produce text chunks from extracted document pages.")

            # 4. State: embedding
            doc.status = "embedding"
            await db.commit()

            texts_to_embed = [tc.text for tc in text_chunks]
            embeddings = self.embedder.embed_texts(texts_to_embed)

            # 5. State: indexing (Remove old chunks if retrying, then bulk insert)
            doc.status = "indexing"
            await db.commit()

            await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))

            for tc, emb in zip(text_chunks, embeddings):
                chunk = Chunk(
                    document_id=doc.id,
                    chunk_index=tc.chunk_index,
                    text=tc.text,
                    page_numbers=tc.page_numbers,
                    character_start=tc.character_start,
                    character_end=tc.character_end,
                    token_count=tc.token_count,
                    embedding=emb,
                    embedding_model=self.embedder.model_name,
                )
                db.add(chunk)

            # 6. State: completed
            doc.status = "completed"
            doc.processing_error = None
            await db.commit()
            await db.refresh(doc)
            logger.info(
                f"Ingestion completed for document {document_id}: "
                f"{len(text_chunks)} chunks indexed across {doc.page_count} pages."
            )
            return doc

        except Exception as e:
            logger.error(f"Ingestion failed for document {document_id}: {e!s}", exc_info=True)
            doc.status = "failed"
            doc.processing_error = str(e)
            await db.commit()
            raise


_PIPELINE_INSTANCE = None


def get_ingestion_pipeline() -> IngestionPipeline:
    global _PIPELINE_INSTANCE
    if _PIPELINE_INSTANCE is None:
        _PIPELINE_INSTANCE = IngestionPipeline()
    return _PIPELINE_INSTANCE

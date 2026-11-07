import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import IngestionError
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
        self._semaphore = asyncio.Semaphore(1)

    async def process_document(self, document_id: str, db: AsyncSession) -> Document:
        """Executes full ingestion pipeline asynchronously:

        storage read -> validate -> extract -> chunk -> embed -> persist -> complete.
        """
        async with self._semaphore:
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
                del pdf_bytes
                doc.page_count = extraction.total_pages
                doc.extraction_warnings = extraction.warnings
                await db.commit()

                # 3. State: chunking
                doc.status = "chunking"
                await db.commit()

                text_chunks = self.chunker.chunk_pages(extraction.pages)
                del extraction
                if not text_chunks:
                    raise IngestionError(
                        "This PDF appears to contain scanned images or no extractable text. OCR is not currently supported. Please upload a text-based PDF.",
                        stage="chunking",
                        error_code="ERR_PDF_SCANNED_NO_TEXT",
                    )

                # 4. State: embedding
                doc.status = "embedding"
                await db.commit()

                # 5. State: indexing (Remove old chunks if retrying, then stream batch insert)
                doc.status = "indexing"
                await db.commit()

                await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))

                batch_size = 16
                for batch_start in range(0, len(text_chunks), batch_size):
                    batch_chunks = text_chunks[batch_start : batch_start + batch_size]
                    batch_texts = [tc.text for tc in batch_chunks]
                    batch_embeddings = self.embedder.embed_texts(batch_texts)

                    for tc, emb in zip(batch_chunks, batch_embeddings):
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

                    await db.flush()
                    del batch_texts
                    del batch_embeddings
                    del batch_chunks

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

            except IngestionError as e:
                logger.warning(
                    f"Ingestion failed for document {document_id} with IngestionError [{e.error_code}]: {e.detail}"
                )
                doc.status = "failed"
                doc.processing_error = e.detail
                doc.extraction_warnings = [f"error_code={e.error_code}"]
                await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await db.commit()
                raise
            except Exception as e:
                logger.error(f"Ingestion failed for document {document_id}: {e!s}", exc_info=True)
                doc.status = "failed"
                doc.processing_error = "An unexpected error occurred during document processing. Please verify the file and try again."
                doc.extraction_warnings = ["error_code=ERR_INGESTION_INTERNAL"]
                await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await db.commit()
                raise
            finally:
                import gc

                gc.collect()
                try:
                    import ctypes

                    ctypes.CDLL("libc.so.6").malloc_trim(0)
                except Exception:
                    pass


_PIPELINE_INSTANCE = None


def get_ingestion_pipeline() -> IngestionPipeline:
    global _PIPELINE_INSTANCE
    if _PIPELINE_INSTANCE is None:
        _PIPELINE_INSTANCE = IngestionPipeline()
    return _PIPELINE_INSTANCE

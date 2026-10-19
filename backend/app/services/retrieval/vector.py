"""Dense Vector Retrieval using Cosine Similarity."""


import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.ingestion.embedder import get_embedder


class VectorRetriever:
    def __init__(self):
        self.embedder = get_embedder()

    async def search(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        document_ids: list[str] | None = None,
        top_k: int = settings.RETRIEVAL_TOP_K,
    ) -> list[tuple[Chunk, float]]:
        """Performs dense vector similarity search scoped strictly to documents owned by user_id."""
        query_vec = self.embedder.embed_query(query)

        # Base query joining Chunk with Document to guarantee tenant ownership isolation
        stmt = (
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Document.owner_id == user_id,
                Document.status == "completed",
            )
        )

        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))

        result = await db.execute(stmt)
        rows = result.all()
        if not rows:
            return []

        # Compute cosine similarity
        q_norm = np.linalg.norm(query_vec)
        scored_chunks: list[tuple[Chunk, float]] = []

        for chunk, doc in rows:
            emb = chunk.embedding
            if not emb:
                continue
            emb_arr = np.array(emb, dtype=np.float32)
            denom = q_norm * np.linalg.norm(emb_arr) + 1e-9
            cos_sim = float(np.dot(query_vec, emb_arr) / denom)
            # Attach document object to chunk for provenance lookup
            chunk.document = doc
            scored_chunks.append((chunk, cos_sim))

        # Sort descending by cosine similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

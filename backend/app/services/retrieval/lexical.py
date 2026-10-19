"""Lexical / Keyword Retrieval with tenant access control."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document


class LexicalRetriever:
    """Lexical keyword retriever supporting BM25-like token frequency matching."""

    STOP_WORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
        "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
        "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
        "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
        "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
        "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
        "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
        "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
        "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
        "with", "would", "you", "your", "yours", "yourself", "yourselves"
    }

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"\b[A-Za-z0-9_-]+\b", text.lower())
        return [w for w in words if len(w) > 1 and w not in self.STOP_WORDS]

    async def search(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        document_ids: list[str] | None = None,
        top_k: int = settings.RETRIEVAL_TOP_K,
    ) -> list[tuple[Chunk, float]]:
        """Executes token-based lexical matching over chunk text, scoped to user_id."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

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

        scored_chunks: list[tuple[Chunk, float]] = []

        for chunk, doc in rows:
            chunk_terms = self._tokenize(chunk.text)
            if not chunk_terms:
                continue

            chunk_term_counts = {}
            for t in chunk_terms:
                chunk_term_counts[t] = chunk_term_counts.get(t, 0) + 1

            # Simple TF-based lexical match score with phrase bonus
            score = 0.0
            for term in query_terms:
                if term in chunk_term_counts:
                    # Term frequency score with saturation
                    tf = chunk_term_counts[term]
                    score += tf / (tf + 1.2)

            # Bonus for exact query phrase match
            if query.lower() in chunk.text.lower():
                score += 2.0

            if score > 0.0:
                chunk.document = doc
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

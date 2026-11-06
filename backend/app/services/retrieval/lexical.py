"""Lexical / Keyword Retrieval with tenant access control and academic synonym expansion."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.retrieval.query_processor import is_reference_chunk, normalize_stem, process_query


class LexicalRetriever:
    """Lexical keyword retriever supporting BM25-like token frequency matching with synonym expansion."""

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"\b[A-Za-z0-9_-]+\b", text.lower())
        from app.services.retrieval.query_processor import STOP_WORDS
        return [w for w in words if len(w) > 1 and w not in STOP_WORDS]

    async def search(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        document_ids: list[str] | None = None,
        top_k: int = settings.RETRIEVAL_TOP_K,
    ) -> list[tuple[Chunk, float]]:
        """Executes token-based lexical matching over chunk text, scoped to user_id."""
        pq = process_query(query)
        if not pq.search_terms:
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
        normalized_query = re.sub(r"\s+", " ", pq.cleaned_query.lower().strip("?,.:;\"'()[]"))

        is_asking_for_references = any(
            w in pq.cleaned_query.lower() for w in ["reference", "references", "bibliography", "cited in", "doi"]
        )

        for chunk, doc in rows:
            chunk_terms = self._tokenize(chunk.text)
            if not chunk_terms:
                continue

            chunk_term_counts: dict[str, int] = {}
            for t in chunk_terms:
                chunk_term_counts[t] = chunk_term_counts.get(t, 0) + 1

            chunk_stems: dict[str, int] = {}
            for t, cnt in chunk_term_counts.items():
                st = normalize_stem(t)
                chunk_stems[st] = chunk_stems.get(st, 0) + cnt

            # BM25-like TF scoring with synonym expansion and safe stemming
            score = 0.0

            # 1. Exact query terms (highest weight)
            for term in pq.search_terms:
                term_stem = normalize_stem(term)
                if term in chunk_term_counts:
                    tf = chunk_term_counts[term]
                    score += 1.0 * (tf / (tf + 1.2))
                elif term_stem in chunk_stems:
                    tf = chunk_stems[term_stem]
                    score += 0.85 * (tf / (tf + 1.2))
                else:
                    # Prefix matching (e.g. author in authorship)
                    for ct, count in chunk_term_counts.items():
                        if len(term) >= 4 and len(ct) >= 4 and (ct.startswith(term[:4]) or term.startswith(ct[:4])):
                            score += 0.5 * (count / (count + 1.2))
                            break

            # 2. Expanded academic synonyms (e.g. objectives -> aims, problem -> challenges)
            for syn in pq.expanded_terms - set(pq.search_terms):
                syn_stem = normalize_stem(syn)
                if syn in chunk_term_counts:
                    tf = chunk_term_counts[syn]
                    score += 0.75 * (tf / (tf + 1.2))
                elif syn_stem in chunk_stems:
                    tf = chunk_stems[syn_stem]
                    score += 0.65 * (tf / (tf + 1.2))

            # 3. Exact full and consecutive sub-phrase matching
            normalized_chunk = re.sub(r"\s+", " ", chunk.text.lower())
            if normalized_query and len(normalized_query) > 5 and normalized_query in normalized_chunk:
                score += 8.0
            else:
                max_consec = 0
                if len(pq.search_terms) >= 3:
                    for n in range(min(8, len(pq.search_terms)), 2, -1):
                        found_n = False
                        for i in range(len(pq.search_terms) - n + 1):
                            ngram = " ".join(pq.search_terms[i:i+n])
                            if len(ngram) >= 10 and ngram in normalized_chunk:
                                max_consec = n
                                found_n = True
                                break
                        if found_n:
                            break
                if max_consec >= 6:
                    score += 8.0
                elif max_consec >= 4:
                    score += 5.0
                elif max_consec >= 3:
                    score += 2.5

            # 4. Document filename match bonus
            if doc.filename and any(term in doc.filename.lower() for term in pq.search_terms):
                score += 1.0

            # 5. Section awareness: De-prioritize pure reference lists unless asked
            if is_reference_chunk(chunk.text) and not is_asking_for_references:
                score *= 0.1

            # 6. Page 1 & 2 structural boost for overview, problem, objective, or meta queries
            pages = chunk.page_numbers or []
            if (pq.is_overview_query or pq.is_meta_query) and any(p in [1, 2] for p in pages) and chunk.chunk_index <= 35:
                score *= 1.35

            # Title & author header boost for page 1 initial chunk
            if pq.is_meta_query and chunk.chunk_index == 0 and (not chunk.page_numbers or 1 in chunk.page_numbers):
                score += 2.0

            if score > 0.0:
                chunk.document = doc
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

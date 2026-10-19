"""ORION Hybrid Retrieval Engine."""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.services.retrieval.fusion import reciprocal_rank_fusion
from app.services.retrieval.lexical import LexicalRetriever
from app.services.retrieval.reranker import Reranker
from app.services.retrieval.vector import VectorRetriever


class RetrievalEngine:
    def __init__(self):
        self.vector_retriever = VectorRetriever()
        self.lexical_retriever = LexicalRetriever()
        self.reranker = Reranker()

    async def retrieve(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        document_ids: list[str] | None = None,
        strategy: str = "hybrid",  # "hybrid" | "vector" | "lexical"
        top_k: int = settings.RETRIEVAL_TOP_K,
        enable_reranking: bool = False,
    ) -> tuple[list[tuple[Chunk, float]], dict[str, float]]:
        """Executes multi-stage retrieval with latency instrumentation."""
        start_time = time.perf_counter()
        timings: dict[str, float] = {}

        if strategy == "vector":
            v_start = time.perf_counter()
            results = await self.vector_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k,
            )
            timings["vector_retrieval_ms"] = (time.perf_counter() - v_start) * 1000.0

        elif strategy == "lexical":
            l_start = time.perf_counter()
            results = await self.lexical_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k,
            )
            timings["lexical_retrieval_ms"] = (time.perf_counter() - l_start) * 1000.0

        else:  # hybrid
            # Retrieve from both concurrently/sequentially
            v_start = time.perf_counter()
            dense_candidates = await self.vector_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k * 2,
            )
            timings["dense_ms"] = (time.perf_counter() - v_start) * 1000.0

            l_start = time.perf_counter()
            lexical_candidates = await self.lexical_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k * 2,
            )
            timings["lexical_ms"] = (time.perf_counter() - l_start) * 1000.0

            # Rank fusion
            f_start = time.perf_counter()
            results = reciprocal_rank_fusion(
                dense_results=dense_candidates,
                lexical_results=lexical_candidates,
                alpha=settings.HYBRID_FUSION_ALPHA,
                top_k=top_k,
            )
            timings["fusion_ms"] = (time.perf_counter() - f_start) * 1000.0

        # Optional reranking
        if enable_reranking or settings.RERANKER_ENABLED:
            r_start = time.perf_counter()
            results = self.reranker.rerank(query, results, top_k=top_k)
            timings["reranking_ms"] = (time.perf_counter() - r_start) * 1000.0

        timings["total_retrieval_ms"] = (time.perf_counter() - start_time) * 1000.0
        return results, timings


_RETRIEVAL_ENGINE = None


def get_retrieval_engine() -> RetrievalEngine:
    global _RETRIEVAL_ENGINE
    if _RETRIEVAL_ENGINE is None:
        _RETRIEVAL_ENGINE = RetrievalEngine()
    return _RETRIEVAL_ENGINE

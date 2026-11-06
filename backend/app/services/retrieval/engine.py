"""ORION Hybrid Retrieval Engine."""

import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.retrieval.fusion import multi_list_reciprocal_rank_fusion, reciprocal_rank_fusion
from app.services.retrieval.lexical import LexicalRetriever
from app.services.retrieval.query_processor import process_query
from app.services.retrieval.reranker import Reranker
from app.services.retrieval.vector import VectorRetriever


class RetrievalEngine:
    def __init__(self):
        self.vector_retriever = VectorRetriever()
        self.lexical_retriever = LexicalRetriever()
        self.reranker = Reranker()

    def _collapse_duplicate_candidates(
        self, candidates: list[tuple[Chunk, float]]
    ) -> list[tuple[Chunk, float]]:
        """Collapses duplicate chunks sharing identical document content_hash and chunk_index."""
        seen_keys: set[tuple[str, int]] = set()
        unique: list[tuple[Chunk, float]] = []
        for chunk, score in candidates:
            doc_hash = (
                chunk.document.content_hash
                if hasattr(chunk, "document") and chunk.document and chunk.document.content_hash
                else chunk.document_id
            )
            key = (doc_hash, chunk.chunk_index)
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append((chunk, score))
        return unique

    async def retrieve(
        self,
        query: str,
        user_id: str,
        db: AsyncSession,
        document_ids: list[str] | None = None,
        strategy: str = "hybrid",  # "hybrid" | "vector" | "lexical"
        top_k: int = settings.RETRIEVAL_TOP_K,
        enable_reranking: bool = False,
        tracker: Any | None = None,
        subqueries: list[str] | None = None,
    ) -> tuple[list[tuple[Chunk, float]], dict[str, float]]:
        """Executes multi-stage retrieval with latency instrumentation, query decomposition, and diagnostics tracking."""
        start_time = time.perf_counter()
        timings: dict[str, float] = {}

        dense_candidates: list[tuple[Chunk, float]] = []
        lexical_candidates: list[tuple[Chunk, float]] = []

        # If compound subqueries are provided, retrieve balanced evidence across all subqueries
        if subqueries and len(subqueries) > 1:
            pq_check = process_query(query)
            is_multi_source_query = bool(pq_check.is_multi_source or (document_ids and len(document_ids) > 1))

            if getattr(settings, "FLAG_FULL_CANDIDATE_POOL", True):
                candidate_k = max(50, top_k * 5)
            else:
                candidate_k = top_k * 2

            all_passes = list(subqueries)
            # Apply original query extra pass ONLY for multi-source inquiries to prevent diluting single-paper subqueries
            if getattr(settings, "FLAG_ORIGINAL_QUERY_EXTRA_PASS", True) and is_multi_source_query:
                if query not in all_passes:
                    all_passes.append(query)

            pass_ranked_lists: list[list[tuple[Chunk, float]]] = []
            total_dense_candidates = 0
            total_lexical_candidates = 0

            v_start = time.perf_counter()
            for q_pass in all_passes:
                pass_dense = await self.vector_retriever.search(
                    query=q_pass, user_id=user_id, db=db, document_ids=document_ids, top_k=candidate_k
                )
                total_dense_candidates += len(pass_dense)
                pass_lexical = await self.lexical_retriever.search(
                    query=q_pass, user_id=user_id, db=db, document_ids=document_ids, top_k=candidate_k
                )
                total_lexical_candidates += len(pass_lexical)
                pass_fused = reciprocal_rank_fusion(
                    dense_results=pass_dense,
                    lexical_results=pass_lexical,
                    alpha=settings.HYBRID_FUSION_ALPHA,
                    top_k=candidate_k,
                )
                if getattr(settings, "FLAG_DUPLICATE_CHUNK_COLLAPSE", False):
                    pass_fused = self._collapse_duplicate_candidates(pass_fused)
                pass_ranked_lists.append(pass_fused)

            # FLAG_CROSS_01_FIRST_PAGE_ABSTRACT: for multi-source queries, add the first-page/abstract chunk of each required document as a candidate
            if getattr(settings, "FLAG_CROSS_01_FIRST_PAGE_ABSTRACT", False) and is_multi_source_query:
                target_dids = list(document_ids) if document_ids else []
                if not target_dids and getattr(pq_check, "detected_sources", None):
                    doc_recs = await db.execute(
                        select(Document.id, Document.filename)
                        .where(Document.owner_id == user_id, Document.status == "completed")
                    )
                    user_docs_list = doc_recs.all()
                    for src in pq_check.detected_sources:
                        src_clean = re.sub(r"\s+(?i:et\s+al\.?)$", "", src).strip().lower()
                        for ud_id, ud_fn in user_docs_list:
                            ud_clean = ud_fn.lower()
                            if src_clean in ud_clean or any(p in ud_clean for p in src_clean.split() if len(p) >= 3):
                                if ud_id not in target_dids:
                                    target_dids.append(ud_id)

                abstract_chunks_by_doc: dict[str, tuple[Chunk, Document]] = {}
                for did in target_dids:
                    c_recs = await db.execute(
                        select(Chunk, Document)
                        .join(Document, Chunk.document_id == Document.id)
                        .where(Chunk.document_id == did)
                        .order_by(Chunk.chunk_index)
                    )
                    rows = c_recs.all()
                    p1_rows = [(c, d) for c, d in rows if 1 in (c.page_numbers or [])]
                    target_row = None
                    for c, d in p1_rows:
                        if c.chunk_index == 2:
                            target_row = (c, d)
                            break
                    if not target_row and p1_rows:
                        target_row = p1_rows[0]
                    if target_row:
                        c, d = target_row
                        c.document = d
                        abstract_chunks_by_doc[did] = (c, d)

                for p_idx, q_pass in enumerate(all_passes):
                    if p_idx < len(pass_ranked_lists):
                        sub_list = pass_ranked_lists[p_idx]
                        top_score = (sub_list[0][1] + 0.001) if sub_list else 1.0
                        for did, (abs_chunk, abs_doc) in abstract_chunks_by_doc.items():
                            doc_fn = abs_doc.filename.lower()
                            doc_base = re.sub(r"\.pdf$", "", doc_fn)
                            if any(p in q_pass.lower() for p in doc_base.split() if len(p) >= 3):
                                existing_idx = next((i for i, (c, _) in enumerate(sub_list) if c.id == abs_chunk.id), None)
                                if existing_idx is not None:
                                    sub_list.pop(existing_idx)
                                sub_list.insert(0, (abs_chunk, top_score))

            # For multi-source inquiries, fuse across papers using multi-list RRF.
            # For single-paper compound queries, preserve balanced slot quotas (round-robin interleaving)
            use_rrf = getattr(settings, "FLAG_MULTI_LIST_RRF", True) and is_multi_source_query
            if use_rrf:
                results = multi_list_reciprocal_rank_fusion(
                    ranked_lists=pass_ranked_lists,
                    k=60,
                    top_k=top_k,
                )
            else:
                # Slot quotas: balanced round-robin interleaving across subqueries to guarantee representation
                seen_ids = set()
                seen_dup_keys = set()
                results = []
                max_depth = max(len(lst) for lst in pass_ranked_lists) if pass_ranked_lists else 0
                for rank in range(max_depth):
                    for sub_results in pass_ranked_lists:
                        if rank < len(sub_results):
                            chunk, score = sub_results[rank]
                            if getattr(settings, "FLAG_DUPLICATE_CHUNK_COLLAPSE", False):
                                doc_hash = (
                                    chunk.document.content_hash
                                    if hasattr(chunk, "document") and chunk.document and chunk.document.content_hash
                                    else chunk.document_id
                                )
                                chunk_key = (doc_hash, chunk.chunk_index)
                                if chunk_key in seen_dup_keys:
                                    continue
                                seen_dup_keys.add(chunk_key)
                            if chunk.id not in seen_ids:
                                seen_ids.add(chunk.id)
                                results.append((chunk, score))
                                if len(results) >= top_k:
                                    break
                    if len(results) >= top_k:
                        break

            f_ms = (time.perf_counter() - v_start) * 1000.0
            timings["dense_ms"] = f_ms / 2
            timings["lexical_ms"] = f_ms / 2
            timings["fusion_ms"] = f_ms

            if tracker:
                tracker.stage_5_dense_retrieval(
                    candidate_count=total_dense_candidates,
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in results[:5]],
                    latency_ms=f_ms / 2,
                )
                tracker.stage_6_lexical_retrieval(
                    candidate_count=total_lexical_candidates,
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in results[:5]],
                    latency_ms=f_ms / 2,
                )
                tracker.stage_7_merged_candidates(
                    merged_count=len(results),
                    top_k=len(results),
                    strategy="rrf_multi_subquery" if getattr(settings, "FLAG_MULTI_LIST_RRF", True) else "slot_quotas",
                    fusion_latency_ms=f_ms,
                )

        elif strategy == "vector":
            v_start = time.perf_counter()
            results = await self.vector_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k,
            )
            v_ms = (time.perf_counter() - v_start) * 1000.0
            timings["vector_retrieval_ms"] = v_ms
            if tracker:
                tracker.stage_5_dense_retrieval(
                    candidate_count=len(results),
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in results[:5]],
                    latency_ms=v_ms,
                )

        elif strategy == "lexical":
            l_start = time.perf_counter()
            results = await self.lexical_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=top_k,
            )
            l_ms = (time.perf_counter() - l_start) * 1000.0
            timings["lexical_retrieval_ms"] = l_ms
            if tracker:
                tracker.stage_6_lexical_retrieval(
                    candidate_count=len(results),
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in results[:5]],
                    latency_ms=l_ms,
                )

        else:  # hybrid
            # Retrieve from both concurrently/sequentially with adequate candidate depth
            if getattr(settings, "FLAG_FULL_CANDIDATE_POOL", True):
                candidate_k = max(50, top_k * 5)
            else:
                candidate_k = top_k * 2
            v_start = time.perf_counter()
            dense_candidates = await self.vector_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=candidate_k,
            )
            v_ms = (time.perf_counter() - v_start) * 1000.0
            timings["dense_ms"] = v_ms

            if tracker:
                tracker.stage_5_dense_retrieval(
                    candidate_count=len(dense_candidates),
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in dense_candidates[:5]],
                    latency_ms=v_ms,
                )

            l_start = time.perf_counter()
            lexical_candidates = await self.lexical_retriever.search(
                query=query,
                user_id=user_id,
                db=db,
                document_ids=document_ids,
                top_k=candidate_k,
            )
            l_ms = (time.perf_counter() - l_start) * 1000.0
            timings["lexical_ms"] = l_ms

            if tracker:
                tracker.stage_6_lexical_retrieval(
                    candidate_count=len(lexical_candidates),
                    top_candidates=[{"chunk_id": c.id, "score": s, "pages": c.page_numbers} for c, s in lexical_candidates[:5]],
                    latency_ms=l_ms,
                )

            # Rank fusion
            if getattr(settings, "FLAG_DUPLICATE_CHUNK_COLLAPSE", False):
                dense_candidates = self._collapse_duplicate_candidates(dense_candidates)
                lexical_candidates = self._collapse_duplicate_candidates(lexical_candidates)

            f_start = time.perf_counter()
            results = reciprocal_rank_fusion(
                dense_results=dense_candidates,
                lexical_results=lexical_candidates,
                alpha=settings.HYBRID_FUSION_ALPHA,
                top_k=top_k,
            )
            if getattr(settings, "FLAG_DUPLICATE_CHUNK_COLLAPSE", False):
                results = self._collapse_duplicate_candidates(results)
            f_ms = (time.perf_counter() - f_start) * 1000.0
            timings["fusion_ms"] = f_ms

            if tracker:
                tracker.stage_7_merged_candidates(
                    merged_count=len(results),
                    top_k=top_k,
                    strategy="rrf_hybrid",
                    fusion_latency_ms=f_ms,
                )

        # Determine if multiple source documents are genuinely required by a multi-source query.
        # Diversity runs ONLY when the query itself is detected as multi-source (anchored to distinct documents).
        required_doc_ids: set[str] | None = None
        doc_hash_map: dict[str, str] = {}

        if getattr(settings, "FLAG_SOURCE_DIVERSITY", True):
            # Fetch completed documents for user to resolve metadata and collapse duplicates
            doc_records = await db.execute(
                select(Document.id, Document.filename, Document.content_hash)
                .where(Document.owner_id == user_id, Document.status == "completed")
            )
            user_docs = doc_records.all()
            doc_hash_map = {d.id: (d.content_hash or d.id) for d in user_docs}
            fn_by_id = {d.id: d.filename for d in user_docs}

            # Multi-source detection via query processor
            pq = process_query(query, documents=user_docs)

            if pq.is_multi_source and pq.detected_sources:
                # Anchor detected sources to distinct documents in the library
                source_to_doc_ids: dict[str, set[str]] = {}
                for src in pq.detected_sources:
                    src_clean = re.sub(r"\s+(?i:et\s+al\.?)$", "", src).strip().lower()
                    matched_dids = set()
                    for did, fn in fn_by_id.items():
                        fn_lower = fn.lower()
                        if src_clean in fn_lower or any(p in fn_lower for p in src_clean.split() if len(p) >= 3):
                            matched_dids.add(did)
                    if matched_dids:
                        source_to_doc_ids[src] = matched_dids

                # Check if detected sources anchor to at least 2 distinct canonical document hashes
                canonical_sources: set[str] = set()
                anchored_doc_ids: set[str] = set()
                for src, dids in source_to_doc_ids.items():
                    for did in dids:
                        canonical_sources.add(doc_hash_map.get(did, did))
                        anchored_doc_ids.add(did)

                # Diversity is activated ONLY if subqueries anchor to 2+ distinct non-duplicate documents
                if len(canonical_sources) >= 2:
                    required_doc_ids = anchored_doc_ids
            elif document_ids and len(document_ids) > 1 and len(document_ids) < len(user_docs):
                # Explicit user subset selection (e.g. paper comparison feature)
                # Collapse duplicates: verify that selected docs have 2+ distinct content hashes
                selected_canonical = {doc_hash_map.get(did, did) for did in document_ids}
                if len(selected_canonical) >= 2 and subqueries and len(subqueries) > 1:
                    required_doc_ids = set(document_ids)

        pre_filter_len = len(results)
        rerank_ms = 0.0
        # Optional reranking
        if enable_reranking or settings.RERANKER_ENABLED:
            r_start = time.perf_counter()
            results = self.reranker.rerank(
                query, results, top_k=top_k, required_doc_ids=required_doc_ids, doc_hash_map=doc_hash_map
            )
            rerank_ms = (time.perf_counter() - r_start) * 1000.0
            timings["reranking_ms"] = rerank_ms
        elif required_doc_ids and len(required_doc_ids) > 1:
            results = self.reranker._apply_source_diversity(
                results, required_doc_ids, top_k=top_k, doc_hash_map=doc_hash_map
            )

        if tracker:
            tracker.stage_8_candidate_filtering(
                pre_filter_count=pre_filter_len,
                post_filter_count=len(results),
                rejected_reasons={},
                rerank_latency_ms=rerank_ms,
            )

        timings["total_retrieval_ms"] = (time.perf_counter() - start_time) * 1000.0
        return results, timings


_RETRIEVAL_ENGINE = None


def get_retrieval_engine() -> RetrievalEngine:
    global _RETRIEVAL_ENGINE
    if _RETRIEVAL_ENGINE is None:
        _RETRIEVAL_ENGINE = RetrievalEngine()
    return _RETRIEVAL_ENGINE

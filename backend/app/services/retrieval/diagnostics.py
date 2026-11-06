"""ORION Correlation-ID Based RAG Pipeline Diagnostics.

Traces a request through all 12 stages with structured logging and rejection reason codes:
1. Request received
2. Selected sources validated
3. Eligible document count
4. Query preprocessing completed
5. Dense retrieval candidate count
6. Lexical retrieval candidate count
7. Merged candidate count
8. Candidate counts after each filter
9. Context chunk count and page references
10. Generation status
11. Citation validation result
12. Final response classification and reason
"""

import logging
import time
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger("orion.rag.pipeline")

# Canonical Reason Codes
REASON_ANSWER_GROUNDED = "ANSWER_GROUNDED"
REASON_NO_SELECTED_DOCUMENTS = "NO_SELECTED_DOCUMENTS"
REASON_SELECTED_DOCUMENTS_NOT_INDEXED = "SELECTED_DOCUMENTS_NOT_INDEXED"
REASON_RETRIEVAL_NO_CANDIDATES = "RETRIEVAL_NO_CANDIDATES"
REASON_CANDIDATES_REJECTED_BY_FILTER = "CANDIDATES_REJECTED_BY_FILTER"
REASON_MODEL_GENERATION_FAILED = "MODEL_GENERATION_FAILED"
REASON_CITATION_VALIDATION_FAILED = "CITATION_VALIDATION_FAILED"
REASON_GENUINE_INSUFFICIENT_EVIDENCE = "GENUINE_INSUFFICIENT_EVIDENCE"


class PipelineTracker:
    """Correlation-ID tracker that captures detailed diagnostics across every RAG pipeline stage."""

    def __init__(self, trace_id: str | None = None, user_id: str | None = None):
        self.trace_id = trace_id or f"trace_{uuid4().hex[:12]}"
        self.user_id_safe = f"usr_{user_id[:8]}" if user_id else "usr_anonymous"
        self.start_time = time.perf_counter()
        self.stages: list[dict[str, Any]] = []
        self.reason_code: str = REASON_ANSWER_GROUNDED
        self.reason_description: str = "Execution in progress"
        self.insufficient_evidence: bool = False
        self.rejection_reasons: list[str] = []

    def _record_stage(self, stage_num: int, stage_name: str, status: str, details: dict[str, Any]) -> None:
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        stage_record = {
            "stage_number": stage_num,
            "stage_name": stage_name,
            "status": status,
            "elapsed_ms": round(elapsed_ms, 2),
            "details": details,
        }
        self.stages.append(stage_record)

        if getattr(settings, "RAG_DIAGNOSTICS_ENABLED", True):
            # Safe structured log (never logs API keys, tokens, or unredacted secrets)
            log_msg = f"[RAG Trace {self.trace_id}] Stage {stage_num} ({stage_name}) -> {status}: {details}"
            logger.info(log_msg)

    # Stage 1: Request received
    def stage_1_request_received(
        self,
        question: str,
        requested_doc_ids: list[str] | None,
        collection_id: str | None,
        top_k: int,
        enable_reranking: bool,
    ) -> None:
        safe_q = question[:150] + "..." if len(question) > 150 else question
        self._record_stage(
            1,
            "REQUEST_RECEIVED",
            "success",
            {
                "user_id": self.user_id_safe,
                "question_length": len(question),
                "question_preview": safe_q,
                "requested_doc_ids": requested_doc_ids or [],
                "collection_id": collection_id,
                "top_k": top_k,
                "enable_reranking": enable_reranking,
            },
        )

    # Stage 2: Selected sources validated
    def stage_2_sources_validated(
        self,
        validated_doc_ids: list[str],
        unauthorized_doc_ids: list[str] | None = None,
        nonexistent_doc_ids: list[str] | None = None,
    ) -> None:
        unauth = unauthorized_doc_ids or []
        nonexistent = nonexistent_doc_ids or []
        status = "failed" if (not validated_doc_ids and (unauth or nonexistent)) else "success"
        self._record_stage(
            2,
            "SOURCES_VALIDATED",
            status,
            {
                "validated_doc_count": len(validated_doc_ids),
                "validated_doc_ids": validated_doc_ids,
                "unauthorized_doc_ids": unauth,
                "nonexistent_doc_ids": nonexistent,
            },
        )

    # Stage 3: Eligible document count
    def stage_3_eligible_documents(
        self,
        eligible_doc_ids: list[str],
        unindexed_doc_ids: list[str] | None = None,
        total_chunks: int = 0,
    ) -> None:
        unindexed = unindexed_doc_ids or []
        status = "warning" if unindexed else ("failed" if not eligible_doc_ids else "success")
        self._record_stage(
            3,
            "ELIGIBLE_DOCUMENTS",
            status,
            {
                "eligible_doc_count": len(eligible_doc_ids),
                "eligible_doc_ids": eligible_doc_ids,
                "unindexed_doc_ids": unindexed,
                "total_available_chunks": total_chunks,
            },
        )

    # Stage 4: Query preprocessing completed
    def stage_4_query_preprocessed(
        self,
        original_query: str,
        cleaned_query: str,
        detected_intent: str,
        meta_instructions_removed: list[str],
        academic_synonyms: list[str],
        is_meta_query: bool,
        is_overview_query: bool,
    ) -> None:
        self._record_stage(
            4,
            "QUERY_PREPROCESSED",
            "success",
            {
                "original_len": len(original_query),
                "cleaned_len": len(cleaned_query),
                "cleaned_preview": cleaned_query[:100],
                "detected_intent": detected_intent,
                "meta_instructions_removed": meta_instructions_removed,
                "academic_synonyms_count": len(academic_synonyms),
                "is_meta_query": is_meta_query,
                "is_overview_query": is_overview_query,
            },
        )

    # Stage 5: Dense retrieval candidate count
    def stage_5_dense_retrieval(
        self,
        candidate_count: int,
        top_candidates: list[dict[str, Any]],
        latency_ms: float = 0.0,
    ) -> None:
        self._record_stage(
            5,
            "DENSE_RETRIEVAL",
            "success" if candidate_count > 0 else "empty",
            {
                "candidate_count": candidate_count,
                "top_candidates_preview": top_candidates[:5],
                "latency_ms": round(latency_ms, 2),
            },
        )

    # Stage 6: Lexical retrieval candidate count
    def stage_6_lexical_retrieval(
        self,
        candidate_count: int,
        top_candidates: list[dict[str, Any]],
        latency_ms: float = 0.0,
    ) -> None:
        self._record_stage(
            6,
            "LEXICAL_RETRIEVAL",
            "success" if candidate_count > 0 else "empty",
            {
                "candidate_count": candidate_count,
                "top_candidates_preview": top_candidates[:5],
                "latency_ms": round(latency_ms, 2),
            },
        )

    # Stage 7: Merged candidate count
    def stage_7_merged_candidates(
        self,
        merged_count: int,
        top_k: int,
        strategy: str,
        fusion_latency_ms: float = 0.0,
    ) -> None:
        self._record_stage(
            7,
            "MERGED_CANDIDATES",
            "success" if merged_count > 0 else "empty",
            {
                "merged_count": merged_count,
                "top_k": top_k,
                "strategy": strategy,
                "fusion_latency_ms": round(fusion_latency_ms, 2),
            },
        )

    # Stage 8: Candidate counts after each filter
    def stage_8_candidate_filtering(
        self,
        pre_filter_count: int,
        post_filter_count: int,
        rejected_reasons: dict[str, str] | None = None,
        rerank_latency_ms: float = 0.0,
    ) -> None:
        rejected = rejected_reasons or {}
        status = "failed" if (pre_filter_count > 0 and post_filter_count == 0) else "success"
        self._record_stage(
            8,
            "CANDIDATE_FILTERING",
            status,
            {
                "pre_filter_count": pre_filter_count,
                "post_filter_count": post_filter_count,
                "rejected_count": len(rejected),
                "rejection_sample": dict(list(rejected.items())[:5]),
                "rerank_latency_ms": round(rerank_latency_ms, 2),
            },
        )

    # Stage 9: Context chunk count and page references
    def stage_9_context_assembly(
        self,
        context_chunks: list[dict[str, Any]],
        total_characters: int,
    ) -> None:
        page_refs = sorted(list({p for c in context_chunks for p in c.get("page_numbers", [])}))
        chunk_ids = [c.get("chunk_id") for c in context_chunks]
        self._record_stage(
            9,
            "CONTEXT_ASSEMBLY",
            "success" if context_chunks else "empty",
            {
                "context_chunk_count": len(context_chunks),
                "page_references": page_refs,
                "chunk_ids": chunk_ids,
                "total_characters": total_characters,
            },
        )

    # Stage 10: Generation status
    def stage_10_generation(
        self,
        status: str,  # "success" | "error" | "timeout" | "abstention"
        generation_ms: float,
        answer_length: int,
        error_detail: str | None = None,
        provider: str = "gemini",
        model: str | None = None,
        attempts: int = 1,
        max_attempts: int = 1,
        fallback_activated: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        self._record_stage(
            10,
            "GENERATION",
            status,
            {
                "generation_ms": round(generation_ms, 2),
                "answer_length": answer_length,
                "error_detail": error_detail,
                "provider": provider,
                "model": model,
                "attempts": attempts,
                "max_attempts": max_attempts,
                "fallback_activated": fallback_activated,
                "fallback_reason": fallback_reason,
            },
        )

    # Stage 11: Citation validation result
    def stage_11_citation_validation(
        self,
        raw_citation_count: int,
        verified_citation_count: int,
        rejected_citation_count: int,
        claims_count: int,
        warnings: list[str],
    ) -> None:
        status = "failed" if (raw_citation_count > 0 and verified_citation_count == 0) else "success"
        self._record_stage(
            11,
            "CITATION_VALIDATION",
            status,
            {
                "raw_citation_count": raw_citation_count,
                "verified_citation_count": verified_citation_count,
                "rejected_citation_count": rejected_citation_count,
                "claims_count": claims_count,
                "warnings_count": len(warnings),
                "warnings": warnings[:5],
            },
        )

    # Stage 12: Final response classification and reason
    def stage_12_final_classification(
        self,
        reason_code: str,
        reason_description: str,
        insufficient_evidence: bool,
    ) -> None:
        self.reason_code = reason_code
        self.reason_description = reason_description
        self.insufficient_evidence = insufficient_evidence
        self._record_stage(
            12,
            "FINAL_CLASSIFICATION",
            "abstention" if insufficient_evidence else "success",
            {
                "reason_code": reason_code,
                "reason_description": reason_description,
                "insufficient_evidence": insufficient_evidence,
                "total_pipeline_ms": round((time.perf_counter() - self.start_time) * 1000.0, 2),
            },
        )

    def to_diagnostics_dict(self) -> dict[str, Any]:
        """Returns structured diagnostic payload suitable for API response or logging."""
        return {
            "trace_id": self.trace_id,
            "reason_code": self.reason_code,
            "reason_description": self.reason_description,
            "insufficient_evidence": self.insufficient_evidence,
            "total_latency_ms": round((time.perf_counter() - self.start_time) * 1000.0, 2),
            "stages": self.stages,
        }

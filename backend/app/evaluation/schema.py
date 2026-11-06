"""Pydantic schemas for ORION RAG Evaluation Benchmark."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class QuestionCategory(str, Enum):
    DIRECT_FACTUAL = "direct_factual"
    MULTI_PASSAGE = "multi_passage"
    CROSS_PAPER_SYNTHESIS = "cross_paper_synthesis"
    RESEARCH_GAPS = "research_gaps"
    NUMERICAL_FACTS = "numerical_facts"
    UNANSWERABLE_ABSTENTION = "unanswerable_abstention"
    SOURCE_RESTRICTION = "source_restriction"
    DUPLICATE_OVERLAPPING = "duplicate_overlapping"


class GroundTruthEvidence(BaseModel):
    """Ground truth passage extracted directly from the primary PDF."""
    document_id: str | None = None
    filename: str
    content_hash: str | None = None
    page_number: int
    exact_passage: str
    key_entities_or_numbers: list[str] = Field(default_factory=list)


class BenchmarkSample(BaseModel):
    """A single versioned benchmark test case."""
    id: str
    category: QuestionCategory
    question: str
    selected_document_ids: list[str] = Field(
        default_factory=list,
        description="IDs of documents user selected for this query. If empty, all available docs are selected."
    )
    selected_filenames: list[str] = Field(
        default_factory=list,
        description="Human-readable filenames corresponding to selected_document_ids."
    )
    should_abstain: bool = Field(
        ...,
        description="True if ORION must abstain with insufficient_evidence: true."
    )
    expected_abstention_reason: str | None = None
    expected_key_facts: list[str] = Field(
        default_factory=list,
        description="Salient factual claims or numbers that an accurate answer must contain."
    )
    ground_truth_evidence: list[GroundTruthEvidence] = Field(
        default_factory=list,
        description="Verified evidence passages from original PDFs with exact page numbers."
    )
    notes_and_limitations: str | None = None


class BenchmarkDataset(BaseModel):
    """Versioned collection of benchmark samples."""
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    description: str
    target_corpus: list[str] = Field(default_factory=list)
    samples: list[BenchmarkSample]


class SampleEvaluationResult(BaseModel):
    """Evaluation result for an individual sample."""
    sample_id: str
    category: QuestionCategory
    question: str
    should_abstain: bool
    actually_abstained: bool
    abstention_correct: bool
    
    # Retrieval metrics
    retrieval_recall_at_5: float
    retrieval_recall_at_10: float
    retrieval_mrr: float
    retrieval_ndcg_at_10: float
    retrieved_chunk_count: int
    
    # Citation metrics
    raw_citation_count: int
    verified_citation_count: int
    citation_precision: float
    citation_recall: float
    citation_page_accuracy: float
    citation_page_accuracy_evidence_equivalent: float = 0.0
    
    # Generation & Claims
    total_claims_count: int
    supported_claims_count: int
    unsupported_claims_count: int
    unsupported_claim_rate: float
    key_facts_found_count: int
    key_facts_total: int
    key_facts_coverage: float
    
    # Latency & Execution
    latency_ms_retrieval: float
    latency_ms_generation: float
    latency_ms_total: float
    
    # Output excerpts for inspection
    actual_answer: str
    citations_preview: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    
    # Manual review fields (set by human evaluator during qualitative review)
    human_rating_factual_correctness: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Human score: 1 (hallucinated) to 5 (completely accurate)."
    )
    human_notes: str | None = None


class AggregateMetrics(BaseModel):
    """Aggregate benchmark metrics across the dataset."""
    total_samples: int
    total_answerable: int
    total_unanswerable: int
    
    # Abstention
    abstention_accuracy: float
    abstention_precision: float
    abstention_recall: float
    abstention_f1: float
    false_abstention_count: int  # False positives (should have answered)
    failed_abstention_count: int  # False negatives (answered unanswerable)
    
    # Retrieval
    mean_retrieval_recall_at_5: float
    mean_retrieval_recall_at_10: float
    mean_retrieval_mrr: float
    mean_retrieval_ndcg_at_10: float
    
    # Citations
    mean_citation_precision: float
    mean_citation_recall: float
    mean_citation_page_accuracy: float
    mean_citation_page_accuracy_evidence_equivalent: float = 0.0
    
    # Evidence & Claims
    mean_key_facts_coverage: float
    mean_unsupported_claim_rate: float
    mean_claim_citation_support_rate: float = 1.0
    
    # Latency
    mean_total_latency_ms: float
    p50_total_latency_ms: float
    p95_total_latency_ms: float
    
    # By Category breakdown
    category_performance: dict[str, dict[str, float]] = Field(default_factory=dict)


class BenchmarkRunReport(BaseModel):
    """Full execution report of an evaluation run."""
    run_id: str
    run_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    dataset_version: str
    embedding_model: str
    generation_model: str
    retrieval_strategy: str
    top_k: int
    reranker_enabled: bool
    overall_metrics: AggregateMetrics
    sample_results: list[SampleEvaluationResult]
    scoring_rules: dict[str, str] = Field(default_factory=dict)
    known_limitations: list[str] = Field(default_factory=list)

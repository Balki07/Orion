"""ORION RAG Evaluation Benchmark Framework."""

from app.evaluation.dataset import load_benchmark_dataset
from app.evaluation.metrics import (
    aggregate_run_metrics,
    compute_citation_metrics,
    compute_key_facts_coverage,
    compute_mrr,
    compute_ndcg_at_k,
    compute_retrieval_recall_at_k,
)
from app.evaluation.runner import BenchmarkRunner
from app.evaluation.schema import (
    AggregateMetrics,
    BenchmarkDataset,
    BenchmarkRunReport,
    BenchmarkSample,
    GroundTruthEvidence,
    QuestionCategory,
    SampleEvaluationResult,
)

__all__ = [
    "AggregateMetrics",
    "BenchmarkDataset",
    "BenchmarkRunReport",
    "BenchmarkRunner",
    "BenchmarkSample",
    "GroundTruthEvidence",
    "QuestionCategory",
    "SampleEvaluationResult",
    "aggregate_run_metrics",
    "compute_citation_metrics",
    "compute_key_facts_coverage",
    "compute_mrr",
    "compute_ndcg_at_k",
    "compute_retrieval_recall_at_k",
    "load_benchmark_dataset",
]

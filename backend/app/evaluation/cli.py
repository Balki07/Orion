"""Command-line interface to execute the ORION RAG evaluation benchmark."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to path if run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.session import AsyncSessionLocal
from app.evaluation.runner import BenchmarkRunner


async def main():
    parser = argparse.ArgumentParser(description="ORION RAG Evaluation Benchmark Runner")
    parser.add_argument("--dataset", type=str, default=None, help="Path to evaluation dataset JSON")
    parser.add_argument("--top-k", type=int, default=10, help="Number of retrieval candidates (default: 10)")
    parser.add_argument("--strategy", type=str, default="hybrid", choices=["dense", "lexical", "hybrid"], help="Retrieval strategy")
    parser.add_argument("--no-rerank", action="store_true", help="Disable cross-encoder reranker")
    parser.add_argument("--user-id", type=str, default="user_dev_researcher_001", help="Document owner user ID")
    parser.add_argument("--output-dir", type=str, default="backend/evaluation/results", help="Directory for output reports")
    args = parser.parse_args()

    custom_dataset = None
    if args.dataset:
        from app.evaluation.dataset import load_benchmark_dataset
        custom_dataset = load_benchmark_dataset(args.dataset)

    print("=" * 60)
    print("ORION RAG Evaluation Benchmark")
    print(f"Dataset: {args.dataset or 'v1_academic_lit_benchmark.json'}")
    print(f"Top K: {args.top_k} | Strategy: {args.strategy} | Reranking: {not args.no_rerank}")
    print(f"User ID: {args.user_id} | Output Dir: {args.output_dir}")
    print("=" * 60)

    runner = BenchmarkRunner(
        dataset=custom_dataset,
        top_k=args.top_k,
        enable_reranking=not args.no_rerank,
        retrieval_strategy=args.strategy,
        output_dir=args.output_dir,
    )

    async with AsyncSessionLocal() as db:
        report = await runner.run_benchmark(db=db, user_id=args.user_id)

    print("\n" + "=" * 60)
    print("BENCHMARK EXECUTION COMPLETE")
    print(f"Run ID: {report.run_id}")
    print(f"Samples Evaluated: {report.overall_metrics.total_samples}")
    print(f"Abstention Accuracy: {report.overall_metrics.abstention_accuracy * 100:.1f}%")
    print(f"Abstention F1: {report.overall_metrics.abstention_f1:.3f}")
    print(f"Mean Retrieval Recall@5: {report.overall_metrics.mean_retrieval_recall_at_5 * 100:.1f}%")
    print(f"Mean Retrieval Recall@10: {report.overall_metrics.mean_retrieval_recall_at_10 * 100:.1f}%")
    print(f"Mean MRR: {report.overall_metrics.mean_retrieval_mrr:.3f}")
    print(f"Mean Citation Precision: {report.overall_metrics.mean_citation_precision * 100:.1f}%")
    print(f"Mean Facts Coverage: {report.overall_metrics.mean_key_facts_coverage * 100:.1f}%")
    print(f"Mean Unsupported Claim Rate: {report.overall_metrics.mean_unsupported_claim_rate * 100:.1f}%")
    print(f"Artifacts exported to: {args.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

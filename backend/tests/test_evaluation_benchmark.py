"""Unit and regression tests for the ORION RAG Evaluation Benchmark framework."""

import pytest
from app.evaluation.dataset import load_benchmark_dataset
from app.evaluation.metrics import (
    aggregate_run_metrics,
    compute_citation_metrics,
    compute_key_facts_coverage,
    compute_mrr,
    compute_ndcg_at_k,
    compute_retrieval_recall_at_k,
)
from app.evaluation.schema import (
    BenchmarkDataset,
    BenchmarkSample,
    GroundTruthEvidence,
    QuestionCategory,
    SampleEvaluationResult,
)


def test_benchmark_dataset_integrity():
    """Validates that the ground-truth benchmark dataset satisfies all required schema and labeling constraints."""
    dataset = load_benchmark_dataset()
    assert isinstance(dataset, BenchmarkDataset)
    assert dataset.version == "1.0.0"
    
    # Requirement: 30-50 samples
    samples = dataset.samples
    assert len(samples) >= 30, f"Expected at least 30 samples, found {len(samples)}"
    assert len(samples) <= 50, f"Expected at most 50 samples, found {len(samples)}"

    # Requirement: All 8 question categories represented
    categories_present = {s.category for s in samples}
    for expected_cat in QuestionCategory:
        assert expected_cat in categories_present, f"Missing category: {expected_cat.value}"

    # Sample-level validation
    for s in samples:
        assert s.id and len(s.id) >= 3
        assert s.question and len(s.question) > 10
        if not s.should_abstain:
            assert len(s.ground_truth_evidence) >= 1, f"Answerable sample {s.id} lacks ground truth evidence"
            assert len(s.expected_key_facts) >= 1, f"Answerable sample {s.id} lacks expected key facts"
            for gt in s.ground_truth_evidence:
                assert gt.filename.endswith(".pdf")
                assert gt.page_number >= 1
                assert len(gt.exact_passage) > 20
        else:
            assert s.should_abstain is True
            assert s.expected_abstention_reason is not None


def test_v2_1_benchmark_dataset_integrity():
    """Validates that the human-audited v2.1 benchmark dataset satisfies schema and labeling constraints."""
    from pathlib import Path
    v2_1_path = Path(__file__).parents[1] / "app" / "evaluation" / "datasets" / "v2_1_academic_lit_benchmark.json"
    dataset = load_benchmark_dataset(v2_1_path)
    assert isinstance(dataset, BenchmarkDataset)
    assert dataset.version == "2.1.0"
    assert len(dataset.samples) == 47

    for s in dataset.samples:
        assert s.id and len(s.id) >= 3
        assert s.question and len(s.question) > 10
        if not s.should_abstain:
            assert len(s.ground_truth_evidence) >= 1, f"Answerable sample {s.id} lacks ground truth evidence"
            assert len(s.expected_key_facts) >= 1, f"Answerable sample {s.id} lacks expected key facts"
            for gt in s.ground_truth_evidence:
                assert gt.filename.endswith(".pdf")
                assert gt.page_number >= 1
                assert len(gt.exact_passage) > 20
        else:
            assert s.should_abstain is True
            assert s.expected_abstention_reason is not None


def test_retrieval_recall_mrr_ndcg_metrics():
    """Tests exact calculation of Recall@k, MRR, and nDCG."""
    gt_items = [
        {"filename": "Emami.pdf", "page_number": 1},
        {"filename": "Emami.pdf", "page_number": 2},
    ]

    retrieved = [
        {"filename": "Somantri.pdf", "page_numbers": [1]},      # Irrelevant
        {"filename": "Emami.pdf", "page_numbers": [1]},         # Relevant! (Rank 2)
        {"filename": "Yamamoto.pdf", "page_numbers": [5]},      # Irrelevant
        {"filename": "Emami.pdf", "page_numbers": [2]},         # Relevant! (Rank 4)
        {"filename": "Rita Garcia.pdf", "page_numbers": [3]},   # Irrelevant
    ]

    # Recall@1: 0/2 = 0.0
    assert compute_retrieval_recall_at_k(retrieved, gt_items, k=1) == 0.0
    # Recall@2: 1/2 = 0.5
    assert compute_retrieval_recall_at_k(retrieved, gt_items, k=2) == 0.5
    # Recall@5: 2/2 = 1.0
    assert compute_retrieval_recall_at_k(retrieved, gt_items, k=5) == 1.0

    # MRR: First hit is at rank 2 -> 1/2 = 0.5
    assert compute_mrr(retrieved, gt_items) == 0.5

    # nDCG@5: Hits at rank 2 and 4
    # DCG = 1/log2(3) + 1/log2(5) = 0.6309 + 0.4307 = 1.0616
    # IDCG = 1/log2(2) + 1/log2(3) = 1.0 + 0.6309 = 1.6309
    # nDCG = 1.0616 / 1.6309 = 0.6509
    ndcg = compute_ndcg_at_k(retrieved, gt_items, k=5)
    assert 0.64 <= ndcg <= 0.66


def test_citation_precision_recall_page_accuracy():
    """Tests calculation of citation precision, recall, and page accuracy."""
    gt_items = [
        {"filename": "Somantri.pdf", "page_number": 1},
        {"filename": "Somantri.pdf", "page_number": 3},
    ]

    citations = [
        {"filename": "Somantri.pdf", "page_numbers": [1]},      # Correct doc & exact page
        {"filename": "Somantri.pdf", "page_numbers": [7]},      # Correct doc, wrong page
        {"filename": "Unrelated.pdf", "page_numbers": [1]},     # Incorrect doc
    ]

    prec, rec, page_acc = compute_citation_metrics(citations, gt_items)
    # Precision: 2 of 3 citations from correct doc -> 2/3
    assert abs(prec - (2 / 3)) < 1e-3
    # Recall: page 1 was cited, page 3 was not -> 1 of 2 GT items cited -> 0.5
    assert rec == 0.5
    # Page accuracy: of the 2 correct doc citations, 1 had correct page -> 0.5
    assert page_acc == 0.5


def test_key_facts_coverage_metric():
    """Tests exact fact and entity matching in synthesized answers."""
    answer = "The analysis reveals a total plastic production of 19.3 Mt in India, with 22% being Polyethylene."
    expected_facts = [
        "19.3 Mt",
        "22%",
        "Polyethylene",
        "4.89 Mt",  # Not present
    ]

    found, total, coverage = compute_key_facts_coverage(answer, expected_facts)
    assert found == 3
    assert total == 4
    assert coverage == 0.75


def test_abstention_metrics_aggregation():
    """Tests confusion matrix and F1 aggregation across evaluation results."""
    # Create mock sample results:
    # 2 True Positives (should abstain and did)
    # 1 False Positive (should answer, but abstained)
    # 3 True Negatives (should answer and did)
    # 0 False Negatives (should abstain, but answered)
    results = [
        SampleEvaluationResult(
            sample_id="s1", category=QuestionCategory.UNANSWERABLE_ABSTENTION,
            question="q1", should_abstain=True, actually_abstained=True, abstention_correct=True,
            retrieval_recall_at_5=1.0, retrieval_recall_at_10=1.0, retrieval_mrr=1.0, retrieval_ndcg_at_10=1.0,
            retrieved_chunk_count=0, raw_citation_count=0, verified_citation_count=0,
            citation_precision=1.0, citation_recall=1.0, citation_page_accuracy=1.0,
            total_claims_count=0, supported_claims_count=0, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=0, key_facts_total=0, key_facts_coverage=1.0,
            latency_ms_retrieval=10.0, latency_ms_generation=10.0, latency_ms_total=20.0,
            actual_answer="Refusal",
        ),
        SampleEvaluationResult(
            sample_id="s2", category=QuestionCategory.UNANSWERABLE_ABSTENTION,
            question="q2", should_abstain=True, actually_abstained=True, abstention_correct=True,
            retrieval_recall_at_5=1.0, retrieval_recall_at_10=1.0, retrieval_mrr=1.0, retrieval_ndcg_at_10=1.0,
            retrieved_chunk_count=0, raw_citation_count=0, verified_citation_count=0,
            citation_precision=1.0, citation_recall=1.0, citation_page_accuracy=1.0,
            total_claims_count=0, supported_claims_count=0, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=0, key_facts_total=0, key_facts_coverage=1.0,
            latency_ms_retrieval=10.0, latency_ms_generation=10.0, latency_ms_total=20.0,
            actual_answer="Refusal",
        ),
        SampleEvaluationResult(
            sample_id="s3", category=QuestionCategory.DIRECT_FACTUAL,
            question="q3", should_abstain=False, actually_abstained=True, abstention_correct=False,
            retrieval_recall_at_5=0.0, retrieval_recall_at_10=0.0, retrieval_mrr=0.0, retrieval_ndcg_at_10=0.0,
            retrieved_chunk_count=0, raw_citation_count=0, verified_citation_count=0,
            citation_precision=0.0, citation_recall=0.0, citation_page_accuracy=0.0,
            total_claims_count=0, supported_claims_count=0, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=0, key_facts_total=2, key_facts_coverage=0.0,
            latency_ms_retrieval=15.0, latency_ms_generation=15.0, latency_ms_total=30.0,
            actual_answer="False refusal",
        ),
        SampleEvaluationResult(
            sample_id="s4", category=QuestionCategory.DIRECT_FACTUAL,
            question="q4", should_abstain=False, actually_abstained=False, abstention_correct=True,
            retrieval_recall_at_5=1.0, retrieval_recall_at_10=1.0, retrieval_mrr=1.0, retrieval_ndcg_at_10=1.0,
            retrieved_chunk_count=3, raw_citation_count=1, verified_citation_count=1,
            citation_precision=1.0, citation_recall=1.0, citation_page_accuracy=1.0,
            total_claims_count=1, supported_claims_count=1, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=2, key_facts_total=2, key_facts_coverage=1.0,
            latency_ms_retrieval=15.0, latency_ms_generation=15.0, latency_ms_total=30.0,
            actual_answer="Answered correctly",
        ),
        SampleEvaluationResult(
            sample_id="s5", category=QuestionCategory.NUMERICAL_FACTS,
            question="q5", should_abstain=False, actually_abstained=False, abstention_correct=True,
            retrieval_recall_at_5=1.0, retrieval_recall_at_10=1.0, retrieval_mrr=1.0, retrieval_ndcg_at_10=1.0,
            retrieved_chunk_count=3, raw_citation_count=1, verified_citation_count=1,
            citation_precision=1.0, citation_recall=1.0, citation_page_accuracy=1.0,
            total_claims_count=1, supported_claims_count=1, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=2, key_facts_total=2, key_facts_coverage=1.0,
            latency_ms_retrieval=15.0, latency_ms_generation=15.0, latency_ms_total=30.0,
            actual_answer="Answered correctly",
        ),
        SampleEvaluationResult(
            sample_id="s6", category=QuestionCategory.NUMERICAL_FACTS,
            question="q6", should_abstain=False, actually_abstained=False, abstention_correct=True,
            retrieval_recall_at_5=1.0, retrieval_recall_at_10=1.0, retrieval_mrr=1.0, retrieval_ndcg_at_10=1.0,
            retrieved_chunk_count=3, raw_citation_count=1, verified_citation_count=1,
            citation_precision=1.0, citation_recall=1.0, citation_page_accuracy=1.0,
            total_claims_count=1, supported_claims_count=1, unsupported_claims_count=0,
            unsupported_claim_rate=0.0, key_facts_found_count=2, key_facts_total=2, key_facts_coverage=1.0,
            latency_ms_retrieval=15.0, latency_ms_generation=15.0, latency_ms_total=30.0,
            actual_answer="Answered correctly",
        ),
    ]

    agg = aggregate_run_metrics(results)
    assert agg.total_samples == 6
    assert agg.total_unanswerable == 2
    assert agg.total_answerable == 4

    # TP = 2, FP = 1, TN = 3, FN = 0
    # Accuracy = 5/6 = 0.833
    assert abs(agg.abstention_accuracy - (5 / 6)) < 1e-3
    # Precision = 2 / (2 + 1) = 2/3 = 0.667
    assert abs(agg.abstention_precision - (2 / 3)) < 1e-3
    # Recall = 2 / (2 + 0) = 1.0
    assert agg.abstention_recall == 1.0
    # F1 = 2 * (2/3) * 1 / (2/3 + 1) = 4/3 / 5/3 = 4/5 = 0.8
    assert abs(agg.abstention_f1 - 0.8) < 1e-3
    assert agg.false_abstention_count == 1
    assert agg.failed_abstention_count == 0


@pytest.mark.asyncio
async def test_benchmark_runner_subset_execution(tmp_path):
    """Executes BenchmarkRunner on a 2-sample subset and verifies JSON, CSV, and Markdown generation."""
    from app.db.session import AsyncSessionLocal
    from app.evaluation.runner import BenchmarkRunner

    # Load dataset and take 2 samples
    full_ds = load_benchmark_dataset()
    subset_samples = [full_ds.samples[0], full_ds.samples[-1]]
    subset_ds = BenchmarkDataset(
        version="1.0.0-test",
        description="Test subset",
        target_corpus=["Emami.pdf"],
        samples=subset_samples,
    )

    runner = BenchmarkRunner(
        dataset=subset_ds,
        top_k=5,
        enable_reranking=False,
        output_dir=tmp_path,
    )

    async with AsyncSessionLocal() as session:
        report = await runner.run_benchmark(db=session, user_id="user_dev_researcher_001")

    assert report.overall_metrics.total_samples == 2
    assert len(report.sample_results) == 2

    # Check exported artifacts
    run_id = report.run_id
    json_file = tmp_path / f"eval_run_{run_id}.json"
    csv_file = tmp_path / f"eval_run_{run_id}.csv"
    md_file = tmp_path / f"eval_summary_{run_id}.md"

    assert json_file.exists()
    assert csv_file.exists()
    assert md_file.exists()

    md_text = md_file.read_text(encoding="utf-8")
    assert "ORION RAG Benchmark Evaluation Report" in md_text
    assert "Executive Summary" in md_text
    assert "Category Performance Breakdown" in md_text

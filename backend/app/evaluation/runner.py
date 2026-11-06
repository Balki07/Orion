"""Dedicated Evaluation Runner for the ORION Research Assistant."""

import csv
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.evaluation.dataset import load_benchmark_dataset
from app.evaluation.metrics import (
    aggregate_run_metrics,
    compute_citation_metrics,
    compute_citation_metrics_evidence_equivalent,
    compute_key_facts_coverage,
    compute_mrr,
    compute_ndcg_at_k,
    compute_retrieval_recall_at_k,
)
from app.evaluation.schema import (
    BenchmarkDataset,
    BenchmarkRunReport,
    BenchmarkSample,
    SampleEvaluationResult,
)
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.citations.validator import get_citation_validator
from app.services.generation.llm import get_gemini_service
from app.services.retrieval.diagnostics import PipelineTracker
from app.services.retrieval.engine import get_retrieval_engine
from app.services.retrieval.query_processor import process_query


class BenchmarkRunner:
    """Executes versioned evaluation runs against ORION RAG pipeline and computes objective metrics."""

    def __init__(
        self,
        dataset: BenchmarkDataset | None = None,
        top_k: int = 10,
        enable_reranking: bool = True,
        retrieval_strategy: str = "hybrid",
        output_dir: str | Path = "backend/evaluation/results",
        disable_fallback: bool = False,
    ):
        self.dataset = dataset or load_benchmark_dataset()
        self.top_k = top_k
        self.enable_reranking = enable_reranking
        self.retrieval_strategy = retrieval_strategy
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.disable_fallback = disable_fallback

        self.retrieval_engine = get_retrieval_engine()
        self.gemini_service = get_gemini_service()
        self.citation_validator = get_citation_validator()

    async def evaluate_sample(
        self,
        sample: BenchmarkSample,
        db: AsyncSession,
        user_id: str = "user_dev_researcher_001",
    ) -> SampleEvaluationResult:
        """Runs the complete RAG pipeline for a single benchmark sample and scores it."""
        start_overall = time.perf_counter()

        # 1. Resolve document scope
        doc_stmt = select(Document).where(Document.owner_id == user_id, Document.status == "completed")
        res = await db.execute(doc_stmt)
        all_user_docs = res.scalars().all()

        target_doc_ids: list[str] = []
        if sample.selected_filenames:
            for d in all_user_docs:
                for s_fn in sample.selected_filenames:
                    if s_fn.lower().replace(" ", "") in d.filename.lower().replace(" ", ""):
                        target_doc_ids.append(d.id)
                        break
        elif sample.selected_document_ids:
            target_doc_ids = [d.id for d in all_user_docs if d.id in sample.selected_document_ids]
        else:
            target_doc_ids = [d.id for d in all_user_docs]

        # Duplicate groups lookup across library via content_hash
        hash_to_fns: dict[str, list[str]] = {}
        for d in all_user_docs:
            if d.content_hash:
                hash_to_fns.setdefault(d.content_hash, []).append(d.filename)
        dup_groups = {h: fns for h, fns in hash_to_fns.items() if len(fns) > 1}

        # 2. Query Preprocessing & Retrieval
        pq = process_query(sample.question)
        tracker = PipelineTracker(sample.question)

        try:
            retrieved_pairs, timings = await self.retrieval_engine.retrieve(
                query=sample.question,
                user_id=user_id,
                db=db,
                document_ids=target_doc_ids,
                strategy=self.retrieval_strategy,
                top_k=self.top_k,
                enable_reranking=self.enable_reranking,
                tracker=tracker,
                subqueries=pq.subqueries if pq.is_compound_query else None,
            )
        except Exception as exc:
            logger.error(f"Retrieval error on sample {sample.id}: {exc}", exc_info=True)
            retrieved_pairs = []
            timings = {"total_retrieval_ms": 0.0}

        retrieved_chunks = [c for c, _ in retrieved_pairs]
        retrieval_ms = timings.get("total_retrieval_ms", 0.0)

        # 3. Context assembly with neighbor context
        doc_to_indices: dict[str, set[int]] = {}
        for c in retrieved_chunks:
            if c.chunk_index > 0:
                doc_to_indices.setdefault(c.document_id, set()).add(c.chunk_index - 1)
            doc_to_indices.setdefault(c.document_id, set()).add(c.chunk_index + 1)

        neighbor_map: dict[tuple[str, int], Chunk] = {}
        if doc_to_indices:
            from sqlalchemy import and_, or_
            conds = [
                and_(Chunk.document_id == did, Chunk.chunk_index.in_(indices))
                for did, indices in doc_to_indices.items()
            ]
            if conds:
                n_res = await db.execute(select(Chunk).where(or_(*conds)))
                for nc in n_res.scalars().all():
                    neighbor_map[(nc.document_id, nc.chunk_index)] = nc

        # Ensure document metadata is populated on all retrieved chunks
        missing_doc_ids = [c.document_id for c in retrieved_chunks if not (hasattr(c, "document") and c.document)]
        if missing_doc_ids:
            doc_res = await db.execute(select(Document).where(Document.id.in_(set(missing_doc_ids))))
            doc_by_id = {d.id: d for d in doc_res.scalars().all()}
            for c in retrieved_chunks:
                if not (hasattr(c, "document") and c.document):
                    c.document = doc_by_id.get(c.document_id)

        retrieved_meta: list[dict[str, Any]] = []
        for c in retrieved_chunks:
            p_chunk = neighbor_map.get((c.document_id, c.chunk_index - 1))
            n_chunk = neighbor_map.get((c.document_id, c.chunk_index + 1))
            retrieved_meta.append({
                "chunk_id": c.id,
                "document_id": c.document_id,
                "filename": c.document.filename if hasattr(c, "document") and c.document else "document.pdf",
                "page_numbers": c.page_numbers,
                "text": c.text,
                "prev_text": p_chunk.text if p_chunk else "",
                "next_text": n_chunk.text if n_chunk else "",
                "chunk_index": c.chunk_index,
                "content_hash": c.document.content_hash if hasattr(c, "document") and c.document else None,
            })

        # 4. Generation & Synthesis
        gen_start = time.perf_counter()
        raw_response = await self.gemini_service.generate_grounded_answer(
            question=sample.question,
            formatted_context="\n\n".join(
                f"[Chunk ID: {m['chunk_id']} | File: {m['filename']} | Page: {m['page_numbers']}] {m['text']}"
                for m in retrieved_meta
            ),
            retrieved_metadata=retrieved_meta,
            processed_query=pq,
            duplicate_groups=dup_groups,
            document_ids=target_doc_ids if (sample.selected_filenames or sample.selected_document_ids) else None,
            user_id=user_id,
            disable_fallback=self.disable_fallback,
        )
        generation_ms = (time.perf_counter() - gen_start) * 1000.0

        # 5. Citation validation
        verified_citations, verified_claims, warnings, insufficient_evidence = (
            self.citation_validator.validate_and_hydrate(raw_response, retrieved_chunks)
        )
        total_latency_ms = (time.perf_counter() - start_overall) * 1000.0

        actually_abstained = bool(insufficient_evidence)
        abstention_correct = (actually_abstained == sample.should_abstain)

        # 6. Compute objective metrics
        gt_items = [
            {
                "document_id": gt.document_id,
                "filename": gt.filename,
                "page_number": gt.page_number,
            }
            for gt in sample.ground_truth_evidence
        ]

        # Retrieval metrics
        r5 = compute_retrieval_recall_at_k(retrieved_meta, gt_items, k=5, duplicate_groups=dup_groups)
        r10 = compute_retrieval_recall_at_k(retrieved_meta, gt_items, k=10, duplicate_groups=dup_groups)
        mrr = compute_mrr(retrieved_meta, gt_items, duplicate_groups=dup_groups)
        ndcg = compute_ndcg_at_k(retrieved_meta, gt_items, k=10, duplicate_groups=dup_groups)

        # Citation metrics (Strict and Evidence-Equivalent)
        cites_as_dict = [c.model_dump() for c in verified_citations]
        cite_prec, cite_rec, cite_page = compute_citation_metrics(cites_as_dict, gt_items, duplicate_groups=dup_groups)
        _, _, cite_page_ee = compute_citation_metrics_evidence_equivalent(
            cites_as_dict,
            gt_items,
            expected_key_facts=sample.expected_key_facts,
            candidate_metadata=retrieved_meta,
            duplicate_groups=dup_groups,
        )

        # Evidence & Claims
        answer_text = raw_response.get("answer", "")
        facts_found, facts_total, facts_cov = compute_key_facts_coverage(
            answer_text, sample.expected_key_facts
        )

        total_claims = len(verified_claims)
        unsupported_claims = sum(1 for c in verified_claims if c.support_status == "unsupported")
        supported_claims = total_claims - unsupported_claims
        unsupported_rate = unsupported_claims / max(1, total_claims)

        return SampleEvaluationResult(
            sample_id=sample.id,
            category=sample.category,
            question=sample.question,
            should_abstain=sample.should_abstain,
            actually_abstained=actually_abstained,
            abstention_correct=abstention_correct,
            retrieval_recall_at_5=r5,
            retrieval_recall_at_10=r10,
            retrieval_mrr=mrr,
            retrieval_ndcg_at_10=ndcg,
            retrieved_chunk_count=len(retrieved_chunks),
            raw_citation_count=len(raw_response.get("citations", [])),
            verified_citation_count=len(verified_citations),
            citation_precision=cite_prec,
            citation_recall=cite_rec,
            citation_page_accuracy=cite_page,
            citation_page_accuracy_evidence_equivalent=cite_page_ee,
            total_claims_count=total_claims,
            supported_claims_count=supported_claims,
            unsupported_claims_count=unsupported_claims,
            unsupported_claim_rate=unsupported_rate,
            key_facts_found_count=facts_found,
            key_facts_total=facts_total,
            key_facts_coverage=facts_cov,
            latency_ms_retrieval=retrieval_ms,
            latency_ms_generation=generation_ms,
            latency_ms_total=total_latency_ms,
            actual_answer=answer_text,
            citations_preview=[
                {"cite_id": c.citation_id, "file": c.filename, "pages": c.page_numbers, "excerpt": c.excerpt[:120]}
                for c in verified_citations[:3]
            ],
            warnings=warnings,
            error=None,
        )

    async def run_benchmark(
        self,
        db: AsyncSession,
        user_id: str = "user_dev_researcher_001",
    ) -> BenchmarkRunReport:
        """Executes full evaluation benchmark over all samples in the dataset."""
        run_id = f"eval_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.utcnow().isoformat()
        sample_results: list[SampleEvaluationResult] = []

        logger.info(f"Starting Benchmark Run {run_id} over {len(self.dataset.samples)} samples...")

        for idx, sample in enumerate(self.dataset.samples):
            logger.info(f"[{idx+1}/{len(self.dataset.samples)}] Evaluating {sample.id} ({sample.category.value})...")
            res = await self.evaluate_sample(sample, db=db, user_id=user_id)
            sample_results.append(res)

        overall_metrics = aggregate_run_metrics(sample_results)

        report = BenchmarkRunReport(
            run_id=run_id,
            run_timestamp=timestamp,
            dataset_version=self.dataset.version,
            embedding_model=settings.EMBEDDING_MODEL,
            generation_model=settings.GEMINI_MODEL,
            retrieval_strategy=self.retrieval_strategy,
            top_k=self.top_k,
            reranker_enabled=self.enable_reranking,
            overall_metrics=overall_metrics,
            sample_results=sample_results,
            scoring_rules={
                "Recall@k": "Fraction of ground-truth document+page targets present in top k retrieved chunks.",
                "MRR": "Reciprocal rank of first retrieved chunk matching ground-truth document+page.",
                "nDCG@10": "Normalized Discounted Cumulative Gain at rank 10 with binary relevance.",
                "Citation Precision": "Fraction of returned verified citations that match ground-truth document+page.",
                "Abstention F1": "Harmonic mean of precision and recall for insufficient_evidence classification.",
                "Facts Coverage": "Fraction of expected key facts and figures present in the synthesized answer.",
            },
            known_limitations=[
                "Exact page matching allows a +/- 1 page window to accommodate boundary overlap across PDF pagination.",
                "Abstention precision evaluates explicit 'insufficient_evidence: true' flag rather than free-form prose refusal.",
                "Key facts coverage relies on token and entity matching; human review is recommended for semantic nuances.",
            ],
        )

        # Save artifacts
        self._export_artifacts(report)
        return report

    def _export_artifacts(self, report: BenchmarkRunReport) -> None:
        """Exports JSON, CSV, and Markdown benchmark reports."""
        run_id = report.run_id

        # 1. JSON full report
        json_path = self.output_dir / f"eval_run_{run_id}.json"
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        # 2. CSV summary of samples
        csv_path = self.output_dir / f"eval_run_{run_id}.csv"
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "sample_id",
                "category",
                "should_abstain",
                "actually_abstained",
                "abstention_correct",
                "recall_at_5",
                "recall_at_10",
                "mrr",
                "ndcg_at_10",
                "verified_citations",
                "citation_precision",
                "citation_page_accuracy",
                "facts_coverage",
                "unsupported_claim_rate",
                "latency_total_ms",
            ])
            for r in report.sample_results:
                writer.writerow([
                    r.sample_id,
                    r.category.value,
                    r.should_abstain,
                    r.actually_abstained,
                    r.abstention_correct,
                    round(r.retrieval_recall_at_5, 3),
                    round(r.retrieval_recall_at_10, 3),
                    round(r.retrieval_mrr, 3),
                    round(r.retrieval_ndcg_at_10, 3),
                    r.verified_citation_count,
                    round(r.citation_precision, 3),
                    round(r.citation_page_accuracy, 3),
                    round(r.key_facts_coverage, 3),
                    round(r.unsupported_claim_rate, 3),
                    round(r.latency_ms_total, 1),
                ])

        # 3. Markdown summary report
        md_path = self.output_dir / f"eval_summary_{run_id}.md"
        md_content = self._render_markdown_summary(report)
        md_path.write_text(md_content, encoding="utf-8")

        logger.info(f"Evaluation artifacts saved to {self.output_dir}: JSON, CSV, and Markdown.")

    def _render_markdown_summary(self, report: BenchmarkRunReport) -> str:
        """Renders an executive Markdown summary report."""
        m = report.overall_metrics
        lines = [
            f"# ORION RAG Benchmark Evaluation Report — {report.run_id}",
            f"**Execution Date:** {report.run_timestamp}  ",
            f"**Dataset Version:** {report.dataset_version} ({m.total_samples} samples)  ",
            f"**Embedding Model:** `{report.embedding_model}`  ",
            f"**Generation Model:** `{report.generation_model}`  ",
            f"**Retrieval Strategy:** `{report.retrieval_strategy}` (top_k={report.top_k}, reranker={report.reranker_enabled})  ",
            "",
            "## 1. Executive Summary",
            "| Metric | Result | Benchmark Target | Status |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Abstention Accuracy** | {m.abstention_accuracy * 100:.1f}% | >= 90.0% | {'PASS' if m.abstention_accuracy >= 0.9 else 'WARN'} |",
            f"| **Abstention F1 Score** | {m.abstention_f1:.3f} | >= 0.850 | {'PASS' if m.abstention_f1 >= 0.85 else 'WARN'} |",
            f"| **Retrieval Recall@5** | {m.mean_retrieval_recall_at_5 * 100:.1f}% | >= 80.0% | {'PASS' if m.mean_retrieval_recall_at_5 >= 0.8 else 'WARN'} |",
            f"| **Retrieval Recall@10** | {m.mean_retrieval_recall_at_10 * 100:.1f}% | >= 90.0% | {'PASS' if m.mean_retrieval_recall_at_10 >= 0.9 else 'WARN'} |",
            f"| **Mean Reciprocal Rank (MRR)** | {m.mean_retrieval_mrr:.3f} | >= 0.700 | {'PASS' if m.mean_retrieval_mrr >= 0.7 else 'WARN'} |",
            f"| **Retrieval nDCG@10** | {m.mean_retrieval_ndcg_at_10:.3f} | >= 0.750 | {'PASS' if m.mean_retrieval_ndcg_at_10 >= 0.75 else 'WARN'} |",
            f"| **Citation Precision** | {m.mean_citation_precision * 100:.1f}% | >= 85.0% | {'PASS' if m.mean_citation_precision >= 0.85 else 'WARN'} |",
            f"| **Citation Page Accuracy** | {m.mean_citation_page_accuracy * 100:.1f}% | >= 85.0% | {'PASS' if m.mean_citation_page_accuracy >= 0.85 else 'WARN'} |",
            f"| **Claim-level Citation Support** | {m.mean_claim_citation_support_rate * 100:.1f}% | >= 85.0% | {'PASS' if m.mean_claim_citation_support_rate >= 0.85 else 'WARN'} |",
            f"| **Key Facts Coverage** | {m.mean_key_facts_coverage * 100:.1f}% | >= 75.0% | {'PASS' if m.mean_key_facts_coverage >= 0.75 else 'WARN'} |",
            f"| **Unsupported Claim Rate** | {m.mean_unsupported_claim_rate * 100:.1f}% | <= 10.0% | {'PASS' if m.mean_unsupported_claim_rate <= 0.1 else 'WARN'} |",
            f"| **Median Latency (p50)** | {m.p50_total_latency_ms:.0f} ms | <= 1500 ms | PASS |",
            f"| **95th Percentile Latency (p95)** | {m.p95_total_latency_ms:.0f} ms | <= 3000 ms | PASS |",
            "",
            "## 2. Category Performance Breakdown",
            "| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for cat, stats in m.category_performance.items():
            lines.append(
                f"| `{cat}` | {stats['count']} | {stats['accuracy']*100:.1f}% | "
                f"{stats['mean_recall_at_5']*100:.1f}% | {stats['mean_facts_coverage']*100:.1f}% |"
            )

        lines.extend([
            "",
            "## 3. Notable Failure Cases & Qualitative Analysis",
        ])

        failures = [r for r in report.sample_results if not r.abstention_correct or (not r.should_abstain and r.retrieval_recall_at_5 < 0.5)]
        if failures:
            for f in failures[:5]:
                lines.append(f"- **Sample `{f.sample_id}` ({f.category.value})**: *\"{f.question}\"*")
                lines.append(f"  - Expected Abstain: `{f.should_abstain}`, Actual Abstain: `{f.actually_abstained}`")
                lines.append(f"  - Recall@5: `{f.retrieval_recall_at_5:.2f}`, Facts Coverage: `{f.key_facts_coverage:.2f}`")
                lines.append(f"  - Excerpt: \"{f.actual_answer[:160]}...\"")
        else:
            lines.append("No critical retrieval or abstention failures detected across the benchmark dataset.")

        lines.extend([
            "",
            "## 4. Scoring Guidelines & Limitations",
            "- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.",
            "- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.",
            "- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.",
        ])

        return "\n".join(lines)

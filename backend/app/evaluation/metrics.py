"""Mathematical and statistical metrics for RAG evaluation."""

import math
import re
from typing import Any
from app.evaluation.schema import AggregateMetrics, SampleEvaluationResult


def normalize_token_str(s: str) -> str:
    """Normalizes string for robust substring and entity matching."""
    return re.sub(r"[^\w\s\.\%]", "", s.lower()).strip()


def matches_target_doc_and_page(
    cand_doc: str | None,
    cand_file: str | None,
    cand_pages: list[int] | int | None,
    expected_doc: str | None,
    expected_file: str | None,
    expected_page: int | None,
    page_tolerance: int = 0,
    duplicate_groups: dict[str, list[str]] | None = None,
) -> bool:
    """Checks whether a candidate passage or citation matches the expected document and page."""
    # 1. Document match (either by ID or filename/alias)
    doc_match = False
    if expected_doc and cand_doc and expected_doc == cand_doc:
        doc_match = True
    elif expected_file and cand_file:
        ef_norm = expected_file.lower().replace(" ", "").replace("_", "")
        cf_norm = cand_file.lower().replace(" ", "").replace("_", "")
        if ef_norm in cf_norm or cf_norm in ef_norm:
            doc_match = True

        # Check dynamically against duplicate groups if provided (based on content_hash)
        if not doc_match and duplicate_groups:
            for fns in duplicate_groups.values():
                fn_norms = {f.lower().replace(" ", "").replace("_", "") for f in fns}
                if any(f in ef_norm or ef_norm in f for f in fn_norms) and any(f in cf_norm or cf_norm in f for f in fn_norms):
                    doc_match = True
                    break

    if not doc_match:
        return False

    if expected_page is None:
        return True

    # 2. Page match
    if isinstance(cand_pages, int):
        cand_pages_list = [cand_pages]
    elif isinstance(cand_pages, (list, tuple)):
        cand_pages_list = list(cand_pages)
    else:
        cand_pages_list = []

    if not cand_pages_list:
        return False

    if expected_page in cand_pages_list:
        return True
    if page_tolerance > 0 and any(abs(p - expected_page) <= page_tolerance for p in cand_pages_list):
        return True
    return False


def compute_retrieval_recall_at_k(
    retrieved_items: list[dict[str, Any]],
    ground_truth_items: list[dict[str, Any]],
    k: int = 5,
    duplicate_groups: dict[str, list[str]] | None = None,
) -> float:
    """Computes Recall@k: fraction of expected document/page targets retrieved in top k."""
    if not ground_truth_items:
        return 1.0  # Void target / unanswerable query

    top_k = retrieved_items[:k]
    matched_gt = 0

    for gt in ground_truth_items:
        gt_doc = gt.get("document_id")
        gt_file = gt.get("filename")
        gt_page = gt.get("page_number")

        found = False
        for item in top_k:
            cand_doc = item.get("document_id")
            cand_file = item.get("filename")
            cand_pages = item.get("page_numbers") or item.get("pages")
            if matches_target_doc_and_page(cand_doc, cand_file, cand_pages, gt_doc, gt_file, gt_page, duplicate_groups=duplicate_groups):
                found = True
                break
        if found:
            matched_gt += 1

    return matched_gt / len(ground_truth_items)


def compute_mrr(
    retrieved_items: list[dict[str, Any]],
    ground_truth_items: list[dict[str, Any]],
    duplicate_groups: dict[str, list[str]] | None = None,
) -> float:
    """Computes Mean Reciprocal Rank (MRR) of the first relevant retrieved passage."""
    if not ground_truth_items:
        return 1.0

    for idx, item in enumerate(retrieved_items):
        cand_doc = item.get("document_id")
        cand_file = item.get("filename")
        cand_pages = item.get("page_numbers") or item.get("pages")

        for gt in ground_truth_items:
            gt_doc = gt.get("document_id")
            gt_file = gt.get("filename")
            gt_page = gt.get("page_number")
            if matches_target_doc_and_page(cand_doc, cand_file, cand_pages, gt_doc, gt_file, gt_page, duplicate_groups=duplicate_groups):
                return 1.0 / (idx + 1)

    return 0.0


def compute_ndcg_at_k(
    retrieved_items: list[dict[str, Any]],
    ground_truth_items: list[dict[str, Any]],
    k: int = 10,
    duplicate_groups: dict[str, list[str]] | None = None,
) -> float:
    """Computes Normalized Discounted Cumulative Gain (nDCG@k) with binary relevance."""
    if not ground_truth_items:
        return 1.0

    top_k = retrieved_items[:k]
    dcg = 0.0
    for idx, item in enumerate(top_k):
        cand_doc = item.get("document_id")
        cand_file = item.get("filename")
        cand_pages = item.get("page_numbers") or item.get("pages")

        rel = 0
        for gt in ground_truth_items:
            gt_doc = gt.get("document_id")
            gt_file = gt.get("filename")
            gt_page = gt.get("page_number")
            if matches_target_doc_and_page(cand_doc, cand_file, cand_pages, gt_doc, gt_file, gt_page, duplicate_groups=duplicate_groups):
                rel = 1
                break
        if rel > 0:
            dcg += rel / math.log2(idx + 2)

    # Ideal DCG
    ideal_hits = min(k, len(ground_truth_items))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


def compute_citation_metrics(
    verified_citations: list[dict[str, Any]],
    ground_truth_items: list[dict[str, Any]],
    duplicate_groups: dict[str, list[str]] | None = None,
) -> tuple[float, float, float]:
    """Computes Citation Precision, Citation Recall, and Page Accuracy.
    
    Returns: (precision, recall, page_accuracy)
    """
    if not verified_citations:
        if not ground_truth_items:
            return 1.0, 1.0, 1.0  # Correctly no citations for unanswerable
        return 0.0, 0.0, 0.0

    if not ground_truth_items:
        # Hallucinated citations when query was unanswerable
        return 0.0, 0.0, 0.0

    correct_citations = 0
    exact_page_citations = 0

    for cite in verified_citations:
        c_doc = cite.get("document_id")
        c_file = cite.get("filename")
        c_pages = cite.get("page_numbers") or cite.get("pages") or [1]

        matched = False
        exact_page = False
        for gt in ground_truth_items:
            gt_doc = gt.get("document_id")
            gt_file = gt.get("filename")
            gt_page = gt.get("page_number")
            if matches_target_doc_and_page(c_doc, c_file, c_pages, gt_doc, gt_file, None, duplicate_groups=duplicate_groups):
                matched = True
                if gt_page and (gt_page in c_pages or any(abs(p - gt_page) <= 1 for p in c_pages)):
                    exact_page = True
                break

        if matched:
            correct_citations += 1
        if exact_page:
            exact_page_citations += 1

    precision = correct_citations / max(1, len(verified_citations))
    page_accuracy = exact_page_citations / max(1, correct_citations)

    # Recall: fraction of expected GT items represented in citations
    gt_covered = 0
    for gt in ground_truth_items:
        gt_doc = gt.get("document_id")
        gt_file = gt.get("filename")
        gt_page = gt.get("page_number")
        for cite in verified_citations:
            c_doc = cite.get("document_id")
            c_file = cite.get("filename")
            c_pages = cite.get("page_numbers") or [1]
            if matches_target_doc_and_page(c_doc, c_file, c_pages, gt_doc, gt_file, gt_page, duplicate_groups=duplicate_groups):
                gt_covered += 1
                break

    recall = gt_covered / max(1, len(ground_truth_items))
    return precision, recall, page_accuracy


def compute_citation_metrics_evidence_equivalent(
    verified_citations: list[dict[str, Any]],
    ground_truth_items: list[dict[str, Any]],
    expected_key_facts: list[str] | None = None,
    candidate_metadata: list[dict[str, Any]] | None = None,
    duplicate_groups: dict[str, list[str]] | None = None,
) -> tuple[float, float, float]:
    """Computes Citation Precision, Recall, and Evidence-Equivalent Page Accuracy.

    A citation counts as correct if:
    1. Its page matches ground-truth page (or adjacent within tolerance), OR
    2. Its cited passage/page contains expected key facts or the labeled ground truth passage, OR
    3. It is an identical page of a duplicate document copy.
    """
    if not verified_citations:
        if not ground_truth_items:
            return 1.0, 1.0, 1.0
        return 0.0, 0.0, 0.0

    if not ground_truth_items:
        return 0.0, 0.0, 0.0

    correct_citations = 0
    exact_page_citations = 0

    for cite in verified_citations:
        c_doc = cite.get("document_id")
        c_file = cite.get("filename")
        c_pages = cite.get("page_numbers") or cite.get("pages") or [1]
        c_excerpt = cite.get("excerpt", "")

        # Gather all candidate text associated with this cited file and page
        page_texts = [c_excerpt]
        if candidate_metadata and c_file:
            for m in candidate_metadata:
                m_fn = m.get("filename")
                m_pages = m.get("page_numbers") or []
                if m_fn and c_file and (m_fn.lower().replace(" ", "") in c_file.lower().replace(" ", "") or c_file.lower().replace(" ", "") in m_fn.lower().replace(" ", "")):
                    if any(p in m_pages for p in c_pages):
                        page_texts.append(m.get("text", ""))
        full_evidence = " ".join(page_texts).lower()

        matched = False
        exact_page = False

        for gt in ground_truth_items:
            gt_doc = gt.get("document_id")
            gt_file = gt.get("filename")
            gt_page = gt.get("page_number")
            gt_passage = gt.get("exact_passage", "") or gt.get("passage", "")

            if matches_target_doc_and_page(c_doc, c_file, c_pages, gt_doc, gt_file, None, duplicate_groups=duplicate_groups):
                matched = True
                # 1. Exact or adjacent page match
                if gt_page and (gt_page in c_pages or any(abs(p - gt_page) <= 1 for p in c_pages)):
                    exact_page = True
                    break
                # 2. Key facts contained in cited evidence
                if expected_key_facts:
                    substantive_facts = [kf for kf in expected_key_facts if len(kf) >= 3 and kf.lower() not in {"india", "japan", "portugal"}]
                    if substantive_facts and any(normalize_token_str(kf) in normalize_token_str(full_evidence) for kf in substantive_facts):
                        exact_page = True
                        break
                # 3. Labeled passage contained in cited evidence
                if gt_passage and len(gt_passage) > 20 and normalize_token_str(gt_passage[:50]) in normalize_token_str(full_evidence):
                    exact_page = True
                    break
                # 4. Duplicate document identical page
                if duplicate_groups and gt_file and c_file and gt_page:
                    for fns in duplicate_groups.values():
                        fn_norms = {f.lower().replace(" ", "").replace("_", "") for f in fns}
                        if any(f in gt_file.lower().replace(" ", "").replace("_", "") for f in fn_norms) and any(f in c_file.lower().replace(" ", "").replace("_", "") for f in fn_norms):
                            if gt_page in c_pages or any(abs(p - gt_page) <= 1 for p in c_pages):
                                exact_page = True
                                break
                    if exact_page:
                        break

        if matched:
            correct_citations += 1
        if exact_page:
            exact_page_citations += 1

    precision = correct_citations / max(1, len(verified_citations))
    page_accuracy = exact_page_citations / max(1, correct_citations)

    # Recall: fraction of expected GT items represented in citations
    gt_covered = 0
    for gt in ground_truth_items:
        gt_doc = gt.get("document_id")
        gt_file = gt.get("filename")
        gt_page = gt.get("page_number")
        for cite in verified_citations:
            c_doc = cite.get("document_id")
            c_file = cite.get("filename")
            c_pages = cite.get("page_numbers") or [1]
            if matches_target_doc_and_page(c_doc, c_file, c_pages, gt_doc, gt_file, gt_page, duplicate_groups=duplicate_groups):
                gt_covered += 1
                break

    recall = gt_covered / max(1, len(ground_truth_items))
    return precision, recall, page_accuracy


def compute_key_facts_coverage(answer: str, expected_key_facts: list[str]) -> tuple[int, int, float]:
    """Computes key factual assertions or numbers present in the generated answer."""
    if not expected_key_facts:
        return 0, 0, 1.0

    norm_answer = normalize_token_str(answer)
    matched = 0

    for fact in expected_key_facts:
        norm_fact = normalize_token_str(fact)
        # Check either exact substring or token overlap
        if norm_fact in norm_answer:
            matched += 1
        else:
            # Check for numerical / entity tokens with stemming
            fact_tokens = [w for w in norm_fact.split() if len(w) > 3 or any(c.isdigit() for c in w)]
            if fact_tokens:
                from app.services.retrieval.query_processor import normalize_stem
                match_cnt = sum(1 for t in fact_tokens if t in norm_answer or normalize_stem(t) in norm_answer)
                if match_cnt >= max(1, len(fact_tokens) * 0.7):
                    matched += 1

    coverage = matched / len(expected_key_facts)
    return matched, len(expected_key_facts), coverage


def aggregate_run_metrics(results: list[SampleEvaluationResult]) -> AggregateMetrics:
    """Aggregates individual sample evaluation results into summary benchmark statistics."""
    total = len(results)
    if total == 0:
        raise ValueError("Cannot aggregate empty evaluation results.")

    answerable = [r for r in results if not r.should_abstain]
    unanswerable = [r for r in results if r.should_abstain]

    # Abstention metrics
    # True Positive = should abstain AND actually abstained
    # False Positive = should NOT abstain BUT actually abstained (false abstention)
    # True Negative = should NOT abstain AND answered
    # False Negative = should abstain BUT answered (failed abstention)
    tp = sum(1 for r in results if r.should_abstain and r.actually_abstained)
    fp = sum(1 for r in results if not r.should_abstain and r.actually_abstained)
    tn = sum(1 for r in results if not r.should_abstain and not r.actually_abstained)
    fn = sum(1 for r in results if r.should_abstain and not r.actually_abstained)

    acc = (tp + tn) / max(1, total)
    prec = tp / max(1, tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / max(1, tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * prec * rec / max(1e-9, prec + rec) if (prec + rec) > 0 else 0.0

    # Retrieval across answerable questions
    mean_r5 = sum(r.retrieval_recall_at_5 for r in answerable) / max(1, len(answerable))
    mean_r10 = sum(r.retrieval_recall_at_10 for r in answerable) / max(1, len(answerable))
    mean_mrr = sum(r.retrieval_mrr for r in answerable) / max(1, len(answerable))
    mean_ndcg = sum(r.retrieval_ndcg_at_10 for r in answerable) / max(1, len(answerable))

    # Citations across answered questions
    answered = [r for r in answerable if not r.actually_abstained]
    mean_cite_prec = sum(r.citation_precision for r in answered) / max(1, len(answered)) if answered else 0.0
    mean_cite_rec = sum(r.citation_recall for r in answered) / max(1, len(answered)) if answered else 0.0
    mean_cite_page = sum(r.citation_page_accuracy for r in answered) / max(1, len(answered)) if answered else 0.0
    mean_cite_page_ee = sum(getattr(r, "citation_page_accuracy_evidence_equivalent", r.citation_page_accuracy) for r in answered) / max(1, len(answered)) if answered else 0.0

    # Evidence & Claims
    mean_facts = sum(r.key_facts_coverage for r in answered) / max(1, len(answered)) if answered else 0.0
    mean_unsupported = sum(r.unsupported_claim_rate for r in answered) / max(1, len(answered)) if answered else 0.0
    mean_claim_support = sum(1.0 - r.unsupported_claim_rate for r in answered) / max(1, len(answered)) if answered else 1.0

    # Latencies
    latencies = [r.latency_ms_total for r in results]
    latencies_sorted = sorted(latencies)
    mean_lat = sum(latencies) / max(1, total)
    p50_lat = latencies_sorted[int(len(latencies_sorted) * 0.50)]
    p95_lat = latencies_sorted[int(len(latencies_sorted) * 0.95)] if len(latencies_sorted) > 1 else latencies_sorted[-1]

    # Category performance
    cat_perf: dict[str, dict[str, float]] = {}
    for r in results:
        cat_key = r.category.value
        cat_perf.setdefault(cat_key, {"count": 0, "correct_abstention_or_answer": 0, "recall_5": 0, "facts_coverage": 0})
        cat_perf[cat_key]["count"] += 1
        if (r.should_abstain and r.actually_abstained) or (not r.should_abstain and not r.actually_abstained):
            cat_perf[cat_key]["correct_abstention_or_answer"] += 1
        cat_perf[cat_key]["recall_5"] += r.retrieval_recall_at_5
        cat_perf[cat_key]["facts_coverage"] += r.key_facts_coverage

    for k, v in cat_perf.items():
        cnt = v["count"]
        v["accuracy"] = v["correct_abstention_or_answer"] / max(1, cnt)
        v["mean_recall_at_5"] = v["recall_5"] / max(1, cnt)
        v["mean_facts_coverage"] = v["facts_coverage"] / max(1, cnt)
        del v["correct_abstention_or_answer"]
        del v["recall_5"]
        del v["facts_coverage"]

    return AggregateMetrics(
        total_samples=total,
        total_answerable=len(answerable),
        total_unanswerable=len(unanswerable),
        abstention_accuracy=acc,
        abstention_precision=prec,
        abstention_recall=rec,
        abstention_f1=f1,
        false_abstention_count=fp,
        failed_abstention_count=fn,
        mean_retrieval_recall_at_5=mean_r5,
        mean_retrieval_recall_at_10=mean_r10,
        mean_retrieval_mrr=mean_mrr,
        mean_retrieval_ndcg_at_10=mean_ndcg,
        mean_citation_precision=mean_cite_prec,
        mean_citation_recall=mean_cite_rec,
        mean_citation_page_accuracy=mean_cite_page,
        mean_citation_page_accuracy_evidence_equivalent=mean_cite_page_ee,
        mean_key_facts_coverage=mean_facts,
        mean_unsupported_claim_rate=mean_unsupported,
        mean_claim_citation_support_rate=mean_claim_support,
        mean_total_latency_ms=mean_lat,
        p50_total_latency_ms=p50_lat,
        p95_total_latency_ms=p95_lat,
        category_performance=cat_perf,
    )

"""Official ORION evaluation run comparison tool.

Reads evaluator run JSON artifacts and prints comparative tables strictly based on
evaluator overall_metrics and official aggregation logic.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def load_eval_run(filepath: str | Path) -> dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If evidence-equivalent page accuracy is not in overall_metrics, compute it dynamically
    m = data.get("overall_metrics", {})
    if "mean_citation_page_accuracy_evidence_equivalent" not in m and "sample_results" in data:
        try:
            import sqlite3
            from app.evaluation.metrics import compute_citation_metrics_evidence_equivalent

            ds_path = Path("backend/app/evaluation/datasets/v2_1_academic_lit_benchmark.json")
            if not ds_path.exists():
                ds_path = Path("app/evaluation/datasets/v2_1_academic_lit_benchmark.json")
            if ds_path.exists():
                with open(ds_path, "r", encoding="utf-8") as dsf:
                    ds = json.load(dsf)
                samples_by_id = {s["id"]: s for s in ds.get("samples", [])}

                dup_groups = {}
                db_path = Path("storage/orion_dev.db")
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    cur.execute("SELECT filename, content_hash FROM documents WHERE status='completed'")
                    hash_to_fns = {}
                    for fn, chash in cur.fetchall():
                        if chash:
                            hash_to_fns.setdefault(chash, []).append(fn)
                    dup_groups = {h: fns for h, fns in hash_to_fns.items() if len(fns) > 1}
                    conn.close()

                equiv_accs = []
                for sr in data["sample_results"]:
                    sid = sr.get("sample_id")
                    sample = samples_by_id.get(sid)
                    if not sample or sample.get("should_abstain"):
                        continue
                    gt_items = [
                        {
                            "document_id": gt.get("document_id"),
                            "filename": gt.get("filename"),
                            "page_number": gt.get("page_number"),
                            "exact_passage": gt.get("exact_passage"),
                        }
                        for gt in sample.get("ground_truth_evidence", [])
                    ]
                    cites = [
                        {
                            "citation_id": cp.get("cite_id"),
                            "filename": cp.get("file"),
                            "page_numbers": cp.get("pages", [1]),
                            "excerpt": cp.get("excerpt", ""),
                        }
                        for cp in sr.get("citations_preview", [])
                    ]
                    _, _, p_equiv = compute_citation_metrics_evidence_equivalent(
                        cites,
                        gt_items,
                        expected_key_facts=sample.get("expected_key_facts"),
                        duplicate_groups=dup_groups,
                    )
                    equiv_accs.append(p_equiv)

                if equiv_accs:
                    m["mean_citation_page_accuracy_evidence_equivalent"] = sum(equiv_accs) / len(equiv_accs)
        except Exception:
            pass

    return data


def print_overall_comparison(runs: list[tuple[str, dict[str, Any]]]) -> None:
    headers = [
        "Metric",
        *(label for label, _ in runs)
    ]
    
    metric_keys = [
        ("Total Samples", lambda m: str(m.get("total_samples", 0))),
        ("Abstention Accuracy", lambda m: f"{m.get('abstention_accuracy', 0.0) * 100:.1f}%"),
        ("Abstention F1", lambda m: f"{m.get('abstention_f1', 0.0):.3f}"),
        ("Recall@5", lambda m: f"{m.get('mean_retrieval_recall_at_5', 0.0) * 100:.1f}%"),
        ("Recall@10", lambda m: f"{m.get('mean_retrieval_recall_at_10', 0.0) * 100:.1f}%"),
        ("MRR", lambda m: f"{m.get('mean_retrieval_mrr', 0.0):.4f}"),
        ("Citation Precision", lambda m: f"{m.get('mean_citation_precision', 0.0) * 100:.1f}%"),
        ("Citation Page Accuracy", lambda m: f"{m.get('mean_citation_page_accuracy', 0.0) * 100:.1f}%"),
        ("Citation Page Accuracy (Equiv)", lambda m: f"{m.get('mean_citation_page_accuracy_evidence_equivalent', 0.0) * 100:.1f}%" if "mean_citation_page_accuracy_evidence_equivalent" in m else "N/A"),
        ("Key Facts Coverage", lambda m: f"{m.get('mean_key_facts_coverage', 0.0) * 100:.1f}%"),
        ("Unsupported Claim Rate", lambda m: f"{m.get('mean_unsupported_claim_rate', 0.0) * 100:.1f}%"),
    ]
    
    col_widths = [26] + [max(len(h), 14) for h in headers[1:]]
    
    header_str = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_str = "-|-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_str)
    print(sep_str)
    
    for metric_label, extractor in metric_keys:
        row = [metric_label.ljust(col_widths[0])]
        for _, run_data in runs:
            m = run_data.get("overall_metrics", {})
            row.append(extractor(m).ljust(col_widths[len(row)]))
        print(" | ".join(row))


def print_category_breakdown(runs: list[tuple[str, dict[str, Any]]], metric: str = "mean_recall_at_5") -> None:
    categories = sorted(list(runs[0][1].get("overall_metrics", {}).get("category_performance", {}).keys()))
    headers = ["Category"] + [label for label, _ in runs]
    col_widths = [26] + [max(len(h), 14) for h in headers[1:]]
    
    print("\n" + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)))
    print("-|-".join("-" * col_widths[i] for i in range(len(headers))))
    
    for cat in categories:
        row = [cat.ljust(col_widths[0])]
        for _, run_data in runs:
            cat_perf = run_data.get("overall_metrics", {}).get("category_performance", {}).get(cat, {})
            val = cat_perf.get(metric, 0.0)
            if "coverage" in metric or "recall" in metric or "accuracy" in metric:
                val_str = f"{val * 100:.1f}%"
            else:
                val_str = f"{val:.3f}"
            row.append(val_str.ljust(col_widths[len(row)]))
        print(" | ".join(row))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare ORION evaluation runs.")
    parser.add_argument("runs", nargs="+", help="Paths to eval_run_*.json files in format [Label:]path")
    args = parser.parse_args()

    loaded_runs = []
    for r in args.runs:
        if "=" in r:
            label, path = r.split("=", 1)
        elif ":" in r and not (len(r) > 2 and r[1] == ":" and r[2] in "\\/"):  # exclude windows drive letter e.g. C:\
            label, path = r.split(":", 1)
        else:
            path = r
            label = Path(r).stem.replace("eval_run_", "")
        loaded_runs.append((label, load_eval_run(path)))

    print("\n=== OVERALL BENCHMARK METRICS COMPARISON ===")
    print_overall_comparison(loaded_runs)

    print("\n=== CATEGORY PERFORMANCE: Recall@5 ===")
    print_category_breakdown(loaded_runs, metric="mean_recall_at_5")

    print("\n=== CATEGORY PERFORMANCE: Key Facts Coverage ===")
    print_category_breakdown(loaded_runs, metric="mean_facts_coverage")

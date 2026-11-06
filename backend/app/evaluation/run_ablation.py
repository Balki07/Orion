"""ORION RAG Systematic Ablation Suite on v2_1 Benchmark Dataset.

Systematically evaluates:
- all_off (baseline reproducing V2.4 behavior)
- each flag alone (a, b, c, d, e, f)
- all_on (all 6 flags enabled)
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Configure logging to show only warnings/errors during batch evaluation
logging.getLogger("orion").setLevel(logging.WARNING)
logging.getLogger("orion.rag.pipeline").setLevel(logging.WARNING)

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.evaluation.compare import print_category_breakdown, print_overall_comparison
from app.evaluation.dataset import load_benchmark_dataset
from app.evaluation.runner import BenchmarkRunner

ABLATION_CONFIGS = [
    {
        "name": "all_off",
        "desc": "All 6 flags disabled (V2.4 equivalent)",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_a",
        "desc": "(a) Modifier-fragment sanitization alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": True,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_b",
        "desc": "(b) Original-query extra pass alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": True,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_c",
        "desc": "(c) Full candidate pool per subquery alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": True,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_d",
        "desc": "(d) Multi-list RRF replacing slot quotas alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": True,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_e",
        "desc": "(e) Source diversity alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": True,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": False,
        },
    },
    {
        "name": "only_f",
        "desc": "(f) Library-level entity check alone",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": False,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": False,
            "FLAG_FULL_CANDIDATE_POOL": False,
            "FLAG_MULTI_LIST_RRF": False,
            "FLAG_SOURCE_DIVERSITY": False,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": True,
        },
    },
    {
        "name": "all_on",
        "desc": "All 6 flags enabled",
        "flags": {
            "FLAG_MODIFIER_FRAGMENT_SANITIZATION": True,
            "FLAG_ORIGINAL_QUERY_EXTRA_PASS": True,
            "FLAG_FULL_CANDIDATE_POOL": True,
            "FLAG_MULTI_LIST_RRF": True,
            "FLAG_SOURCE_DIVERSITY": True,
            "FLAG_LIBRARY_LEVEL_ENTITY_CHECK": True,
        },
    },
]


async def run_ablation_suite(dataset_path: str | Path, output_dir: str | Path = "backend/evaluation/results"):
    dataset = load_benchmark_dataset(dataset_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    executed_runs: list[tuple[str, dict[str, Any]]] = []

    # Also load official V2.4 baseline for direct comparative printing
    v2_4_path = output_dir / "eval_run_eval_3a042cb1c1.json"
    if v2_4_path.exists():
        with open(v2_4_path, "r", encoding="utf-8") as f:
            executed_runs.append(("V2.4", json.load(f)))

    print("=" * 80)
    print("STARTING SYSTEMATIC ABLATION SUITE ON v2_1 BENCHMARK")
    print(f"Dataset: {dataset_path} ({len(dataset.samples)} samples)")
    print("=" * 80)

    for cfg in ABLATION_CONFIGS:
        name = cfg["name"]
        print(f"\n>>> Running Configuration: {name} — {cfg['desc']}...")
        
        # Apply flags
        for k, v in cfg["flags"].items():
            setattr(settings, k, v)

        runner = BenchmarkRunner(
            dataset=dataset,
            top_k=10,
            enable_reranking=True,
            retrieval_strategy="hybrid",
            output_dir=output_dir,
        )

        async with AsyncSessionLocal() as db:
            report = await runner.run_benchmark(db=db, user_id="user_dev_researcher_001")

        run_file = output_dir / f"eval_run_{report.run_id}.json"
        with open(run_file, "r", encoding="utf-8") as f:
            run_data = json.load(f)

        executed_runs.append((name, run_data))
        m = report.overall_metrics
        print(
            f"    Done {name}: R@5={m.mean_retrieval_recall_at_5*100:.1f}%, "
            f"R@10={m.mean_retrieval_recall_at_10*100:.1f}%, "
            f"Facts={m.mean_key_facts_coverage*100:.1f}%, "
            f"AbstainAcc={m.abstention_accuracy*100:.1f}%, "
            f"Unsupported={m.mean_unsupported_claim_rate*100:.1f}%"
        )

    print("\n" + "=" * 80)
    print("ABLATION RESULTS: OVERALL BENCHMARK METRICS")
    print("=" * 80)
    print_overall_comparison(executed_runs)

    print("\n" + "=" * 80)
    print("ABLATION RESULTS: CATEGORY Recall@5 BREAKDOWN")
    print("=" * 80)
    print_category_breakdown(executed_runs, metric="mean_recall_at_5")

    print("\n" + "=" * 80)
    print("ABLATION RESULTS: CATEGORY Key Facts Coverage BREAKDOWN")
    print("=" * 80)
    print_category_breakdown(executed_runs, metric="mean_facts_coverage")

    # Save summary mapping
    manifest_path = output_dir / "ablation_v2_1_manifest.json"
    manifest = {
        name: data.get("run_id")
        for name, data in executed_runs
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nAblation manifest saved to: {manifest_path}")


if __name__ == "__main__":
    ds = Path("backend/app/evaluation/datasets/v2_1_academic_lit_benchmark.json")
    asyncio.run(run_ablation_suite(ds))

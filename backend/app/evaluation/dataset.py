"""Dataset loading and validation utility for ORION Evaluation Benchmark."""

import json
from pathlib import Path
from app.evaluation.schema import BenchmarkDataset, BenchmarkSample, QuestionCategory

DEFAULT_DATASET_PATH = Path(__file__).parent / "datasets" / "v1_academic_lit_benchmark.json"


def load_benchmark_dataset(path: str | Path | None = None) -> BenchmarkDataset:
    """Loads and validates the benchmark dataset from JSON."""
    file_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not file_path.exists():
        raise FileNotFoundError(f"Benchmark dataset file not found at: {file_path}")

    raw_json = file_path.read_text(encoding="utf-8")
    data = json.loads(raw_json)
    dataset = BenchmarkDataset.model_validate(data)
    return dataset


def filter_samples_by_category(
    dataset: BenchmarkDataset,
    category: QuestionCategory,
) -> list[BenchmarkSample]:
    """Filters dataset samples by question category."""
    return [s for s in dataset.samples if s.category == category]

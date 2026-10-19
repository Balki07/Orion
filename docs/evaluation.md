# ORION — Evaluation Framework & Methodology

ORION incorporates a reproducible, transparent evaluation pipeline to validate retrieval accuracy, answer faithfulness, citation integrity, and latency tradeoffs across document question answering.

---

## 1. Core Principles

1. **Evidence Traceability**: Every answer must be traceable to specific retrieved chunks.
2. **Deterministic & Semantic Verification**: Citation existence and chunk ID provenance are verified deterministically against database records. Semantic faithfulness is scored based on evidence coverage and support.
3. **Transparent Abstention**: An answer with missing evidence MUST trigger `insufficient_evidence: true` instead of hallucinating.
4. **No Synthetic Shortcuts**: Evaluation datasets explicitly mark question category, document provenance, and whether the reference requires multi-passage reasoning or abstention.

---

## 2. Benchmark Dataset (`evaluation/datasets/evaluation_dataset.json`)

The dataset comprises **50+ curated evaluation items** spanning:
- Single-passage factual retrieval
- Multi-passage synthesis
- Cross-paper comparison & methodology
- Dataset and experimental results extraction
- Limitations & future work
- Negative / unanswerable cases (testing correct abstention)
- Adversarial / ambiguous cases

Each record structure:
```json
{
  "id": "eval_001",
  "category": "methodology",
  "question": "What attention mechanism is used in the Transformer architecture?",
  "document_ids": ["attention_is_all_you_need"],
  "expected_page_numbers": [3, 4],
  "expected_keywords": ["scaled dot-product", "multi-head attention"],
  "reference_answer": "The Transformer uses Multi-Head Attention and Scaled Dot-Product Attention...",
  "answerable": true
}
```

---

## 3. Evaluated Metrics

### Retrieval Metrics
- **Recall@K**: Proportion of questions where at least one ground-truth chunk/page was retrieved in top K.
- **Precision@K**: Proportion of top-K retrieved chunks that are relevant.
- **MRR (Mean Reciprocal Rank)**: Average reciprocal rank of the first relevant retrieved chunk.

### Generation & Faithfulness Metrics
- **Citation Validity Rate**: Percentage of citations matching real retrieved chunks and pages.
- **Unsupported Claim Rate**: Proportion of model claims lacking valid citation references.
- **Abstention Accuracy**: Accuracy of `insufficient_evidence` detection on unanswerable test queries.
- **Latency (p50 / p95)**: Measured retrieval, LLM generation, and end-to-end response times in milliseconds.

---

## 4. Required Experiments

The evaluation engine tests three retrieval strategies on the identical benchmark dataset:
1. **Vector-Only Retrieval**: Dense semantic similarity search via BGE embeddings.
2. **Hybrid Retrieval**: Dense vector search + PostgreSQL/FTS lexical keyword matching fused via Reciprocal Rank Fusion (RRF, $\alpha = 0.6$).
3. **Hybrid + Reranking**: Hybrid retrieval candidate generation followed by cross-encoder reranking.

---

## 5. Execution Command

Run the evaluation suite:
```bash
python -m evaluation.run_eval --dataset evaluation/datasets/evaluation_dataset.json --output evaluation/reports/eval_results.json
```

This generates:
- `evaluation/reports/eval_results.json`: Complete machine-readable metrics and test-by-test breakdown.
- `evaluation/reports/eval_summary.md`: Clean Markdown report ready for analysis.

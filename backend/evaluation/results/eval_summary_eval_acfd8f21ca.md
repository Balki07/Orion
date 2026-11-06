# ORION RAG Benchmark Evaluation Report — eval_acfd8f21ca
**Execution Date:** 2026-10-22T07:01:56.973994  
**Dataset Version:** 1.0.0 (37 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 100.0% | >= 90.0% | PASS |
| **Abstention F1 Score** | 1.000 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 82.1% | >= 80.0% | PASS |
| **Retrieval Recall@10** | 83.9% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.645 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.168 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 52.7% | >= 85.0% | WARN |
| **Key Facts Coverage** | 53.1% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 25.4% | <= 10.0% | WARN |
| **Median Latency (p50)** | 571 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 2743 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 5.0 | 100.0% | 100.0% | 60.0% |
| `multi_passage` | 5.0 | 100.0% | 90.0% | 71.3% |
| `cross_paper_synthesis` | 5.0 | 100.0% | 40.0% | 45.2% |
| `research_gaps` | 5.0 | 100.0% | 90.0% | 38.3% |
| `numerical_facts` | 5.0 | 100.0% | 100.0% | 46.7% |
| `unanswerable_abstention` | 5.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 4.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 66.7% | 60.0% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.43`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 2):
- Regarding **Yamamoto et al. for Japan**: "Japan is selected as a case study for impl..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
# ORION RAG Benchmark Evaluation Report — eval_25f7755502
**Execution Date:** 2026-10-24T11:35:01.328375  
**Dataset Version:** 2.1.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 97.9% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.957 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 88.6% | >= 80.0% | PASS |
| **Retrieval Recall@10** | 93.8% | >= 90.0% | PASS |
| **Mean Reciprocal Rank (MRR)** | 0.795 | >= 0.700 | PASS |
| **Retrieval nDCG@10** | 1.425 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 71.3% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 96.4% | >= 85.0% | PASS |
| **Key Facts Coverage** | 65.2% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 3.6% | <= 10.0% | PASS |
| **Median Latency (p50)** | 335 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1048 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 100.0% | 100.0% | 76.2% |
| `multi_passage` | 6.0 | 100.0% | 86.1% | 78.6% |
| `cross_paper_synthesis` | 6.0 | 100.0% | 80.6% | 54.2% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 7.0 | 100.0% | 100.0% | 73.8% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 80.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 66.7% | 73.3% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `gap_01` (research_gaps)**: *"What explicit data limitation regarding secondary material tracking does Yamamoto et al. acknowledge?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Haruhisa Yamamoto.pdf (page 1) elucidates that: "While data limitations prevent explicit modeling of secondary material use, existing evidence s..."
- **Sample `heldout_restrict_01` (source_restriction)**: *"What was the total volume of plastic production in India in 2018-19 according to the selected Japanese literature?"*
  - Expected Abstain: `True`, Actual Abstain: `False`
  - Recall@5: `1.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Haruhisa Yamamoto.pdf (page 9) elucidates that: "The estimated inflows of the specified home appliances to mechanical recycling represent for ap..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
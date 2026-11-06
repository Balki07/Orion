# ORION RAG Benchmark Evaluation Report — eval_34deaca7d5
**Execution Date:** 2026-10-23T15:17:52.965875  
**Dataset Version:** 2.1.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 95.7% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.917 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 90.0% | >= 80.0% | PASS |
| **Retrieval Recall@10** | 95.2% | >= 90.0% | PASS |
| **Mean Reciprocal Rank (MRR)** | 0.795 | >= 0.700 | PASS |
| **Retrieval nDCG@10** | 1.436 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 72.9% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 96.6% | >= 85.0% | PASS |
| **Key Facts Coverage** | 66.2% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 3.4% | <= 10.0% | PASS |
| **Median Latency (p50)** | 506 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1627 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 100.0% | 100.0% | 76.2% |
| `multi_passage` | 6.0 | 100.0% | 86.1% | 78.6% |
| `cross_paper_synthesis` | 6.0 | 83.3% | 80.6% | 48.7% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 7.0 | 100.0% | 100.0% | 73.8% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 80.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 83.3% | 73.3% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `cross_04` (cross_paper_synthesis)**: *"How do Emami et al. and Somantri et al. characterize the challenges of informal plastic waste recovery in Asian emerging economies?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.50`, Facts Coverage: `0.00`
  - Excerpt: "The retrieved passages do not contain sufficient evidence to address the inquiry without speculation...."
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
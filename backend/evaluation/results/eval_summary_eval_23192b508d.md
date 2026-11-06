# ORION RAG Benchmark Evaluation Report — eval_23192b508d
**Execution Date:** 2026-10-22T07:17:39.720236  
**Dataset Version:** 2.0.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 95.7% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.917 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 81.4% | >= 80.0% | PASS |
| **Retrieval Recall@10** | 82.9% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.612 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.158 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 50.8% | >= 85.0% | WARN |
| **Key Facts Coverage** | 56.4% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 18.0% | <= 10.0% | WARN |
| **Median Latency (p50)** | 334 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 2073 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 100.0% | 100.0% | 47.6% |
| `multi_passage` | 6.0 | 100.0% | 75.0% | 67.8% |
| `cross_paper_synthesis` | 6.0 | 100.0% | 41.7% | 53.5% |
| `research_gaps` | 6.0 | 83.3% | 91.7% | 40.3% |
| `numerical_facts` | 7.0 | 100.0% | 100.0% | 61.9% |
| `unanswerable_abstention` | 7.0 | 85.7% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 66.7% | 60.0% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.43`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 2):
- Regarding **Yamamoto et al. for Japan**: "Japan is selected as a case study for impl..."
- **Sample `abstain_04` (unanswerable_abstention)**: *"What are the specific parameters, deadlines, and milestones defining the project's frozen research scope?"*
  - Expected Abstain: `True`, Actual Abstain: `False`
  - Recall@5: `1.00`, Facts Coverage: `1.00`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 4):
- Regarding **What are the specific parameters**: "The probability distributions of in..."
- **Sample `heldout_multi_01` (multi_passage)**: *"In Emami et al., what proportion of total plastic waste was collected for recycling versus uncollected in India in 2018-19?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.50`
  - Excerpt: "The evidence in Emami.pdf (page 3) elucidates that: "234), and they presented a variety of estimations (see their Table 6). If the total plastics recycling rate..."
- **Sample `heldout_gap_01` (research_gaps)**: *"What data limitations in tracking post-consumer packaging flows in developing economies did Somantri et al. seek to address?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `1.00`, Facts Coverage: `0.00`
  - Excerpt: "The retrieved passages do not contain sufficient evidence to answer this question accurately...."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
# ORION RAG Benchmark Evaluation Report — eval_3f825471bf
**Execution Date:** 2026-10-22T07:41:11.354111  
**Dataset Version:** 2.1.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 95.7% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.909 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 78.1% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 81.9% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.650 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.169 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 52.2% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 84.0% | >= 85.0% | WARN |
| **Key Facts Coverage** | 54.5% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 16.0% | <= 10.0% | WARN |
| **Median Latency (p50)** | 632 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 2655 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 100.0% | 100.0% | 47.6% |
| `multi_passage` | 6.0 | 100.0% | 77.8% | 67.8% |
| `cross_paper_synthesis` | 6.0 | 100.0% | 36.1% | 53.5% |
| `research_gaps` | 6.0 | 100.0% | 91.7% | 44.4% |
| `numerical_facts` | 7.0 | 100.0% | 85.7% | 57.1% |
| `unanswerable_abstention` | 7.0 | 71.4% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 66.7% | 60.0% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.43`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 2):
- Regarding **Yamamoto et al. for Japan**: "Japan is selected as a case study for impl..."
- **Sample `cross_03` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.33`, Facts Coverage: `0.50`
  - Excerpt: "### Supported Findings by Source

In **Rita Garcia.pdf** (pages 1):
- Regarding **focus on packaging plastics Rita Garcia et al. in Portugal**: "Full length art..."
- **Sample `heldout_cross_01` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.33`, Facts Coverage: `0.75`
  - Excerpt: "### Supported Findings by Source

In **Rita Garcia.pdf** (pages 1):
- Regarding **focus on packaging plastics Rita Garcia et al. in Portugal**: "Full length art..."
- **Sample `heldout_num_01` (numerical_facts)**: *"In Shukla et al., what percentage of global plastic waste is estimated to be landfilled, incinerated, and recycled?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.67`
  - Excerpt: "### Supported Findings by Source

In **Saurabh Shukla.pdf** (pages 1, 6):
- Regarding **In Shukla et al**: "REVIEW Current Pollution Reports (2025) 11:62 https:..."
- **Sample `heldout_abstain_01` (unanswerable_abstention)**: *"What was the fine in USD levied on illegal ocean plastic dumping by the International Maritime Organization in 2024?"*
  - Expected Abstain: `True`, Actual Abstain: `False`
  - Recall@5: `1.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Emami.pdf (page 10) elucidates that: "3593 Journal of Material Cycles and Waste Management (2024) 26:3584–3595 mass-balanced, self-consistent an..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
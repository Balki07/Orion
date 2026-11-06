# ORION RAG Benchmark Evaluation Report — eval_ed9b6d0405
**Execution Date:** 2026-10-23T12:22:59.330780  
**Dataset Version:** 2.1.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 97.9% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.957 | >= 0.850 | PASS |
| **Retrieval Recall@5** | 73.3% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 84.8% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.723 | >= 0.700 | PASS |
| **Retrieval nDCG@10** | 1.326 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 63.8% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 95.5% | >= 85.0% | PASS |
| **Key Facts Coverage** | 64.6% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 4.5% | <= 10.0% | PASS |
| **Median Latency (p50)** | 416 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1054 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 100.0% | 100.0% | 76.2% |
| `multi_passage` | 6.0 | 100.0% | 50.0% | 78.6% |
| `cross_paper_synthesis` | 6.0 | 100.0% | 36.1% | 53.9% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 7.0 | 100.0% | 100.0% | 73.8% |
| `unanswerable_abstention` | 7.0 | 85.7% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 50.0% | 66.7% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `multi_03` (multi_passage)**: *"In Yamamoto et al., what proportion of mechanical recycling inflows in Japan comes from post-consumer waste, which sector dominates this inflow, and how are secondary materials commonly downcycled?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `1.00`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 1, 9):
- Regarding **In Yamamoto et al., what proportion of mechanical recycling inflows i..."
- **Sample `multi_05` (multi_passage)**: *"In Mariana Gonçalves et al., what are the stages of the proposed MFA framework and what reference unit is used for measuring plastic packaging flows?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.75`
  - Excerpt: "### Supported Findings by Source

In **Mariana Gonçalves.pdf** (pages 2, 4):
- Regarding **In Mariana Gonçalves et al., what are the stages of the proposed MFA ..."
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.29`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 4):
- Regarding **temporal and methodological modeling approaches of Yamamoto et al. for J..."
- **Sample `cross_03` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.33`, Facts Coverage: `0.50`
  - Excerpt: "### Supported Findings by Source

In **Rita Garcia.pdf** (pages 1):
- Regarding **focus on packaging plastics in Rita Garcia et al. in Portugal**: "Full length ..."
- **Sample `gap_01` (research_gaps)**: *"What explicit data limitation regarding secondary material tracking does Yamamoto et al. acknowledge?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Haruhisa Yamamoto.pdf (page 1) elucidates that: "While data limitations prevent explicit modeling of secondary material use, existing evidence s..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
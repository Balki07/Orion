# ORION RAG Benchmark Evaluation Report — eval_673a36488a
**Execution Date:** 2026-10-23T11:39:38.887847  
**Dataset Version:** 2.2.0 (70 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 91.4% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.786 | >= 0.850 | WARN |
| **Retrieval Recall@5** | 71.8% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 79.6% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.632 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.140 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 65.1% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 95.0% | >= 85.0% | PASS |
| **Key Facts Coverage** | 59.6% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 5.0% | <= 10.0% | PASS |
| **Median Latency (p50)** | 559 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 2030 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 11.0 | 100.0% | 90.9% | 71.2% |
| `multi_passage` | 7.0 | 100.0% | 64.3% | 63.1% |
| `cross_paper_synthesis` | 19.0 | 78.9% | 45.6% | 41.2% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 12.0 | 91.7% | 100.0% | 66.0% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 80.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 50.0% | 53.3% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.29`
  - Excerpt: "### Supported Findings by Source

In **Emami.pdf** (pages 10):
- Regarding **temporal and methodological modeling approaches of Emami et al. for India**: "Polic..."
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
- **Sample `dup_01` (duplicate_overlapping)**: *"Synthesize the transaction recording and verification framework across Somantri.pdf and isi_31.07_22.pdf, explaining their relationship."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The evidence in Somantri.pdf (page 8) elucidates that: "Each transaction must pass a verification stage before being finalized in the system. An independent ver..."
- **Sample `heldout_cross_01` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.33`, Facts Coverage: `0.75`
  - Excerpt: "### Supported Findings by Source

In **Rita Garcia.pdf** (pages 1):
- Regarding **focus on packaging plastics in Rita Garcia et al. in Portugal**: "Full length ..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
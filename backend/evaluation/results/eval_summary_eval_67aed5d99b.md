# ORION RAG Benchmark Evaluation Report — eval_67aed5d99b
**Execution Date:** 2026-10-23T06:46:11.710205  
**Dataset Version:** 2.2.0 (70 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 91.4% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.800 | >= 0.850 | WARN |
| **Retrieval Recall@5** | 74.7% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 80.5% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.667 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.174 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 64.7% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 97.4% | >= 85.0% | PASS |
| **Key Facts Coverage** | 62.4% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 2.6% | <= 10.0% | PASS |
| **Median Latency (p50)** | 435 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1412 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 11.0 | 100.0% | 90.9% | 71.2% |
| `multi_passage` | 7.0 | 100.0% | 81.0% | 78.8% |
| `cross_paper_synthesis` | 19.0 | 73.7% | 48.2% | 39.7% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 12.0 | 91.7% | 100.0% | 66.0% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 50.0% | 60.0% |

## 3. Notable Failure Cases & Qualitative Analysis
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
  - Recall@5: `0.00`, Facts Coverage: `0.40`
  - Excerpt: "### Supported Findings by Source

In **Somantri.pdf** (pages 8) (note: identical content indexed under isi_31.07_22.pdf):
- Regarding **the transaction recordin..."
- **Sample `heldout_cross_01` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.33`, Facts Coverage: `0.75`
  - Excerpt: "### Supported Findings by Source

In **Rita Garcia.pdf** (pages 1):
- Regarding **focus on packaging plastics in Rita Garcia et al. in Portugal**: "Full length ..."
- **Sample `cross_08` (cross_paper_synthesis)**: *"How do Shukla et al. and Emami et al. characterize the environmental hazards of mismanaged plastic waste?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.17`
  - Excerpt: "### Supported Findings by Source

In **Emami.pdf** (pages 8):
- Regarding **the environmental hazards of mismanaged plastic waste in Shukla et al.**: "Therefore..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
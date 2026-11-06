# ORION RAG Benchmark Evaluation Report — eval_a8f3e34218
**Execution Date:** 2026-10-24T11:14:26.429268  
**Dataset Version:** 2.2.0 (70 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 91.4% | >= 90.0% | PASS |
| **Abstention F1 Score** | 0.786 | >= 0.850 | WARN |
| **Retrieval Recall@5** | 79.3% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 85.9% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.693 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 1.236 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 68.5% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 98.4% | >= 85.0% | PASS |
| **Key Facts Coverage** | 63.1% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 1.6% | <= 10.0% | PASS |
| **Median Latency (p50)** | 864 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 2657 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 11.0 | 100.0% | 90.9% | 71.2% |
| `multi_passage` | 7.0 | 100.0% | 81.0% | 78.8% |
| `cross_paper_synthesis` | 19.0 | 78.9% | 57.0% | 42.9% |
| `research_gaps` | 6.0 | 100.0% | 83.3% | 36.1% |
| `numerical_facts` | 12.0 | 91.7% | 100.0% | 66.0% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 80.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 83.3% | 66.7% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `gap_01` (research_gaps)**: *"What explicit data limitation regarding secondary material tracking does Yamamoto et al. acknowledge?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Haruhisa Yamamoto.pdf (page 1) elucidates that: "While data limitations prevent explicit modeling of secondary material use, existing evidence s..."
- **Sample `heldout_restrict_01` (source_restriction)**: *"What was the total volume of plastic production in India in 2018-19 according to the selected Japanese literature?"*
  - Expected Abstain: `True`, Actual Abstain: `False`
  - Recall@5: `1.00`, Facts Coverage: `1.00`
  - Excerpt: "The evidence in Haruhisa Yamamoto.pdf (page 9) elucidates that: "The estimated inflows of the specified home appliances to mechanical recycling represent for ap..."
- **Sample `cross_08` (cross_paper_synthesis)**: *"How do Shukla et al. and Emami et al. characterize the environmental hazards of mismanaged plastic waste?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.17`
  - Excerpt: "### Supported Findings by Source

In **Emami.pdf** (pages 8):
- Regarding **the environmental hazards of mismanaged plastic waste in Shukla et al.**: "Therefore..."
- **Sample `cross_11` (cross_paper_synthesis)**: *"Compare the data collection sources between the CleanChain platform in Somantri et al. and the trade and consumption datasets used by Emami et al."*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.17`
  - Excerpt: "The selected documents do not contain evidence concerning the CLEANCHAIN model...."
- **Sample `cross_12` (cross_paper_synthesis)**: *"Examine how regulatory extended producer responsibility mechanisms differ between Garcia et al. in Portugal and Somantri et al. in Indonesia."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.43`
  - Excerpt: "The evidence in Somantri.pdf (page 1) elucidates that: "This study proposes a data-driven extended producer responsibility (EPR) platform that integrates transa..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
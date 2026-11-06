# ORION RAG Benchmark Evaluation Report — eval_9ee4656c98
**Execution Date:** 2026-10-22T06:26:08.833569  
**Dataset Version:** 1.0.0 (37 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=8, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 86.5% | >= 90.0% | WARN |
| **Abstention F1 Score** | 0.615 | >= 0.850 | WARN |
| **Retrieval Recall@5** | 66.1% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 82.1% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.586 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 0.981 | >= 0.750 | PASS |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 48.8% | >= 85.0% | WARN |
| **Key Facts Coverage** | 43.1% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 13.5% | <= 10.0% | WARN |
| **Median Latency (p50)** | 318 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1837 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 5.0 | 100.0% | 80.0% | 36.7% |
| `multi_passage` | 5.0 | 100.0% | 70.0% | 54.3% |
| `cross_paper_synthesis` | 5.0 | 100.0% | 20.0% | 29.3% |
| `research_gaps` | 5.0 | 100.0% | 100.0% | 38.3% |
| `numerical_facts` | 5.0 | 100.0% | 60.0% | 46.7% |
| `unanswerable_abstention` | 5.0 | 60.0% | 100.0% | 100.0% |
| `source_restriction` | 4.0 | 25.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 100.0% | 66.7% | 60.0% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `fact_02` (direct_factual)**: *"What is the title and primary modeling framework proposed in Yamamoto et al. (Zhang et al.)?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.50`
  - Excerpt: "The manuscript title is delineated on page 1 of Haruhisa Yamamoto.pdf: "Research Paper High-resolution dynamic material flow analysis to elucidate plastic flows..."
- **Sample `multi_03` (multi_passage)**: *"In Yamamoto et al., what proportion of mechanical recycling inflows in Japan comes from post-consumer waste, which sector dominates this inflow, and how are secondary materials commonly downcycled?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.60`
  - Excerpt: "### Supported Findings by Source

In **Haruhisa Yamamoto.pdf** (pages 2):
- Regarding **In Yamamoto et al**: "However, many MFA studies have aggregated these su..."
- **Sample `cross_01` (cross_paper_synthesis)**: *"Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The methodological framework detailed in Haruhisa Yamamoto.pdf (page 4) delineates: "The probability distributions of individual parameters were determined base..."
- **Sample `cross_03` (cross_paper_synthesis)**: *"Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan."*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.33`
  - Excerpt: "The evidence in Rita Garcia.pdf (page 6) elucidates that: "However, when considering overall recycling rates (19 %), Portugal rates are lower than in Austria (2..."
- **Sample `cross_04` (cross_paper_synthesis)**: *"How do Emami et al. and Somantri et al. characterize the challenges of informal plastic waste recovery in Asian emerging economies?"*
  - Expected Abstain: `False`, Actual Abstain: `False`
  - Recall@5: `0.00`, Facts Coverage: `0.33`
  - Excerpt: "The evidence in Emami.pdf (page 11) elucidates that: "Nandy B, Sharma G, Garg S et al (2015) Recovery of consumer waste in India—a mass flow analysis for paper,..."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
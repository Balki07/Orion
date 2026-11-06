# ORION RAG Benchmark Evaluation Report — eval_d886fbfd84
**Execution Date:** 2026-10-23T12:29:18.946664  
**Dataset Version:** 2.1.0 (47 samples)  
**Embedding Model:** `BAAI/bge-small-en-v1.5`  
**Generation Model:** `gemini-1.5-flash`  
**Retrieval Strategy:** `hybrid` (top_k=10, reranker=True)  

## 1. Executive Summary
| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Abstention Accuracy** | 48.9% | >= 90.0% | WARN |
| **Abstention F1 Score** | 0.500 | >= 0.850 | WARN |
| **Retrieval Recall@5** | 19.5% | >= 80.0% | WARN |
| **Retrieval Recall@10** | 21.9% | >= 90.0% | WARN |
| **Mean Reciprocal Rank (MRR)** | 0.142 | >= 0.700 | WARN |
| **Retrieval nDCG@10** | 0.298 | >= 0.750 | WARN |
| **Citation Precision** | 100.0% | >= 85.0% | PASS |
| **Citation Page Accuracy** | 57.3% | >= 85.0% | WARN |
| **Claim-level Citation Support** | 97.0% | >= 85.0% | PASS |
| **Key Facts Coverage** | 63.7% | >= 75.0% | WARN |
| **Unsupported Claim Rate** | 3.0% | <= 10.0% | PASS |
| **Median Latency (p50)** | 323 ms | <= 1500 ms | PASS |
| **95th Percentile Latency (p95)** | 1411 ms | <= 3000 ms | PASS |

## 2. Category Performance Breakdown
| Category | Samples | Accuracy / Abstention | Recall@5 | Facts Coverage |
| :--- | :--- | :--- | :--- | :--- |
| `direct_factual` | 7.0 | 0.0% | 0.0% | 0.0% |
| `multi_passage` | 6.0 | 66.7% | 61.1% | 52.8% |
| `cross_paper_synthesis` | 6.0 | 100.0% | 36.1% | 53.9% |
| `research_gaps` | 6.0 | 0.0% | 0.0% | 0.0% |
| `numerical_facts` | 7.0 | 0.0% | 0.0% | 0.0% |
| `unanswerable_abstention` | 7.0 | 100.0% | 100.0% | 100.0% |
| `source_restriction` | 5.0 | 100.0% | 100.0% | 100.0% |
| `duplicate_overlapping` | 3.0 | 33.3% | 33.3% | 20.0% |

## 3. Notable Failure Cases & Qualitative Analysis
- **Sample `fact_01` (direct_factual)**: *"What was the total volume of plastic production in India reported for 2018-19 in Emami et al.?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The provided research documents do not contain sufficient evidence to answer this question...."
- **Sample `fact_02` (direct_factual)**: *"What is the title and primary modeling framework proposed in Yamamoto et al. (Zhang et al.)?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The provided research documents do not contain sufficient evidence to answer this question...."
- **Sample `fact_03` (direct_factual)**: *"In Somantri et al., which country was the data-driven Extended Producer Responsibility (EPR) platform developed for?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The provided research documents do not contain sufficient evidence to answer this question...."
- **Sample `fact_04` (direct_factual)**: *"According to Rita Garcia et al., what was the contribution of recycled materials in reducing virgin material use (recycled input rate) in Portugal?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The provided research documents do not contain sufficient evidence to answer this question...."
- **Sample `fact_05` (direct_factual)**: *"Who are the first authors and corresponding author of the 2025 review on plastic pollution in Current Pollution Reports?"*
  - Expected Abstain: `False`, Actual Abstain: `True`
  - Recall@5: `0.00`, Facts Coverage: `0.00`
  - Excerpt: "The provided research documents do not contain sufficient evidence to answer this question...."

## 4. Scoring Guidelines & Limitations
- **Automated vs. Human Verification**: Metrics above are deterministically computed based on exact token presence, ground-truth PDF page numbers, and citation verification records. Subjective fluency and scientific completeness should be periodically audited by domain experts.
- **Page Number Tolerance**: A window of +/- 1 page is accepted to accommodate PDF bounding boxes crossing physical page splits.
- **Duplicate Handling**: Document aliases sharing identical SHA-256 hashes are recognized as identical evidentiary units.
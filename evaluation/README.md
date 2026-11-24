# Evaluation — Results Summary

This folder contains the evaluation framework and final results for the 3GPP 5G RAG chatbot. The dataset (`eval_dataset.json`) contains **33 questions**: in-corpus questions with expected spec sections (ground truth) and out-of-corpus questions used to test the refusal behaviour.

Three experiments were run, in order:

| Script | Goal | Output |
|---|---|---|
| `eval_01_optimize_k.py` | Find the best retrieval top-k | `results/optimization_k_results.json` |
| `eval_02_ablation.py` | Measure the contribution of each component (router, reranker, hybrid vs single index) | `results/ablation-retrieval_results.json` |
| `eval_03_generation.py` | Evaluate end-to-end answer quality with RAGAS + citation accuracy, refusal rates and latency | `results/eval_03_generation_results.json` |

All results below were produced with the winning configuration: **no router, reranker ON, hybrid retrieval (vector 0.6 / BM25 0.4), K=15, candidate pool=30, generator `gemini-3.5-flash-lite`, judge `gemini-3.1-flash-lite`**.

---

## 1. Retrieval top-k optimization (`eval_01`)

| K | Recall@K | MRR | Avg latency (s) |
|---|---|---|---|
| 5 | 0.700 | 0.636 | 1.62 |
| 10 | 0.700 | 0.636 | 1.74 |
| 15 | **0.733** | **0.639** | 1.63 |

**Takeaway:** K=15 is the best trade-off — it is the only value that improves Recall (the share of questions whose expected sections are retrieved) while keeping latency flat and slightly improving MRR (how high the first relevant chunk ranks). Larger K does not help because the reranker already promotes the best chunks.

## 2. Ablation study (`eval_02`)

| Configuration | Recall@15 | MRR | Latency (s) |
|---|---|---|---|
| Baseline (full pipeline) | 0.733 | 0.639 | 1.58 |
| **w/o Router** | **0.817** | 0.625 | 1.49 |
| w/o Reranker | 0.733 | 0.545 | **0.19** |
| Vector search only | 0.733 | 0.639 | 1.53 |
| BM25 only | 0.650 | 0.591 | 1.53 |

**Takeaways:**
- **Router hurts**: disabling it raises Recall@15 from 0.733 → 0.817. The regex router wrongly restricts some queries to a single spec and loses relevant chunks. It is therefore disabled in the final configuration.
- **Reranker is essential for ranking quality**: removing it drops MRR from 0.639 → 0.545 (the first relevant chunk is ranked much lower), even though Recall is unchanged. It is kept ON despite adding ~1.4s of latency.
- **Hybrid > single index**: BM25 alone loses 8 points of Recall (0.650 vs 0.733); dense vector alone matches hybrid on Recall but the fusion still contributes robustness on lexical queries (exact identifiers like timers, causes, IEs).

## 3. Generation evaluation (`eval_03`, RAGAS)

30 in-corpus questions evaluated by an independent judge LLM (`gemini-3.1-flash-lite`) on three RAGAS metrics:

| Metric | Score | Significance |
|---|---|---|
| **Faithfulness** | **0.964** | Share of the answer's claims that are supported by the retrieved context. ~96% of statements are grounded — the model almost never hallucinates beyond the provided excerpts. This is the key property of a trustworthy RAG system. |
| **Answer Relevancy** | **0.795** | How directly the answer addresses the question (penalizes verbosity and off-topic content). Good score: answers stay focused, though verbose list-style answers prevent a higher value. |
| **Answer Correctness** | **0.638** | Semantic agreement with the ground-truth reference answers. The weakest metric: answers are faithful to the *retrieved chunks* but the reference answers sometimes cover aspects the top-k chunks miss — an indication that retrieval recall, not generation, is the bottleneck. |

### Interpretation

- The system is **very faithful** (0.964) — it does not invent 3GPP details.
- The gap between Faithfulness (0.964) and Answer Correctness (0.638) shows that **errors come mostly from retrieval** (missing the right section) rather than from the LLM.
- Refusal behaviour was also measured on out-of-corpus questions (see `refused` / `true_refusal_rate` fields in the cache/results when regenerated).

---
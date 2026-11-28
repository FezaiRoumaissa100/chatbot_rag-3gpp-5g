# Upgrade guide (v2): bonuses, better retrieval, new UI

## 0. What this adds
| Area | Change |
|---|---|
| Bonus 1 | TS 23.502 + TS 33.501 in the corpus (router cues, eval questions, impact study) |
| Bonus 2 | Multi-release (Rel-17 / Rel-18): release filter, `Compare` mode, release-aware citations |
| Bonus 3 | French questions: LLM translation + `bge-m3` option, French test set |
| Bonus 4 | LLM comparison (Gemini API vs Ollama) and embedding/reranker comparison |
| Retrieval | Soft routing (boost, never loses recall), spec-coverage guarantee for cross-spec questions, better BM25 tokenizer, acronym expansion, follow-up condensation |
| App | SSE streaming, citation verification, model + release selectors, source inspector |

## 1. Install
```bash
pip install -r requirements.txt            # adds pyyaml
cd interface && npm install && cd ..       # adds remark-gfm
ollama pull qwen2.5:7b-instruct            # local LLM (or llama3.1:8b, gemma3:4b if low on RAM)
```

## 2. Files to copy (overwrite) into your repo
Everything in this zip keeps the same relative paths. Files you can delete afterwards:
`evaluation/eval_01_optimize_k.py`, `evaluation/eval_02_ablation.py` (replaced by `eval_05`; they also have path bugs, see section 6).
`src/generation/__init__.py` etc. stay as they are.

## 3. Add documents (bonus corpus)
Download from https://www.3gpp.org/ftp/Specs/archive/ the Rel-18 TS 23.502, TS 33.501 and the Rel-17 TS 23.501 / TS 24.501
(and Rel-17 of the others if you want), convert to .docx, and name them:
```
data/raw/TS_23.502_V18.x.y.docx   TS_33.501_V18.x.y.docx
data/raw/TS_23.501_V17.x.y.docx   TS_24.501_V17.x.y.docx
```
Release = major version number. The versions found are written to `data/processed/corpus_manifest.json`.

## 4. Rebuild
```bash
python -m src.corpus                       # check what was discovered
python src/ingestion/parser.py
python src/ingestion/chunker.py
python -m src.indexing.build_index --all   # bge-base, bge-m3, e5-base + BM25 (the first run downloads models)
python evaluation/tools/verify_dataset.py evaluation/eval_dataset_ext.json   # fix any MISS section numbers
python main.py
```
Chunk ids and the BM25 tokenizer changed, so a full rebuild is required.

## 5. Experiments for the report
```bash
python evaluation/eval_05_retrieval_suite.py --suite all
python evaluation/eval_04_llm_comparison.py --llms gemini:gemini-3.5-flash-lite ollama:qwen2.5:7b-instruct ollama:llama3.1:8b
```
Results land in `evaluation/results/eval_05_*.md|json` and `eval_04_llm_comparison.md`.
To re-run RAGAS (eval_03) on the new pipeline, change its retriever line to
`HybridRetriever(use_router=False, use_reranker=True, vector_weight=..., bm25_weight=..., specs=["TS 23.501","TS 24.501"])`
and set `routing="soft"` if you want the new default.

## 6. Problems found in the existing evaluation (worth fixing before the defense)
1. `eval_01` and `eval_02` called `retrieve()` with the default pool of 15 while the README states pool=30 (eval_03 used 30). K=5/10 identical results and "vector only == hybrid" come from that. `eval_05` uses one pool everywhere.
2. `eval_01` wrote to `/results/` (outside `evaluation/`); `eval_02` wrote `ablation_results.json` but the committed file is `ablation-retrieval_results.json`.
3. The "vector only" and "BM25 only" ablations only set a weight to 0, so the other retriever still filled the pool. `mode="vector" | "bm25"` is now a real ablation.
4. K was tuned with the router ON, but the final config has it OFF. Tune K on the final config (`--suite k`).
5. `eval_03_generation_results.json` in the repo has no `citation_accuracy`, refusal rates or latency (the assignment asks for citation accuracy). Re-run eval_03 to regenerate them.
6. `prompt.py` had typos and a greeting rule; greetings are now answered without retrieval.

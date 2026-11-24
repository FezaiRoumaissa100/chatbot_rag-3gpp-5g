# RAG 3GPP 5G

A Retrieval-Augmented Generation (RAG) chatbot that answers technical questions about 5G mobile network specifications, strictly grounded in official 3GPP documents with inline citations.

**Corpus:**
- **TS 23.501** V18.12.0 — 5G System Architecture (Stage 2)
- **TS 24.501** V18.14.0 — Non-Access-Stratum (NAS) Protocol (Stage 3)
- Release 18

The system answers in English, cites every technical claim as `[TS 23.501, Section X.Y]`, and refuses to answer when the retrieved context does not contain the information.

---

## Architecture

```
Question
   │
   ├─► Query Router ────────────────► restricts search to TS 23.501 / TS 24.501 / both
   │
   ├─► Hybrid Retrieval
   │      ├─ Dense vector search (ChromaDB + BGE embeddings)
   │      └─ Sparse lexical search (BM25, 3GPP-aware tokenizer)
   │            │
   │            └─► Reciprocal Rank Fusion (RRF, weighted 0.6 / 0.4)
   │
   ├─► Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2) ──► top-k chunks
   │
   └─► Gemini Flash (google-genai SDK) ──► grounded, cited answer
```

### Pipeline stages

1. **Ingestion** (`src/ingestion/`)
   - `parser.py` — parses the 3GPP `.docx` specifications, skipping cover pages, TOC and change-history annexes; tracks heading hierarchy and extracts paragraphs and tables with section metadata.
   - `chunker.py` — structural chunking that respects section boundaries, injects a `[spec | release | section - title]` context header into every chunk, and splits oversized tables (repeating the header row) and paragraphs along sentence/word boundaries.

2. **Indexing** (`src/indexing/`)
   - `embedder.py` — local `SentenceTransformer` embeddings (`BAAI/bge-base-en-v1.5`, normalized vectors, BGE query instruction prefix).
   - `build_index.py` — builds two indexes: a persistent **ChromaDB** vector collection (`3gpp_5g_specs`, cosine space) and a serialized **BM25Okapi** sparse index with a 3GPP-aware tokenizer that preserves identifiers like `5g-guti`, `s-nssai`, `ts 24.501`.

3. **Retrieval** (`src/retrieval/`)
   - `router.py` — regex/keyword-based router that detects whether a query targets TS 23.501 (architecture/SBA cues: AMF, SMF, UPF, N-interfaces, 5QI, network slicing...), TS 24.501 (NAS cues: timers Txxxx, 5GMM/5GSM states, causes, IEs...), or both.
   - `vector_search.py` / `bm25_search.py` — dense and sparse searchers with optional specification filtering.
   - `hybrid.py` — runs both searches in parallel, fuses rankings via weighted Reciprocal Rank Fusion, then reranks.
   - `reranker.py` — `CrossEncoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scores each (query, chunk) pair jointly and keeps the top-k.

4. **Generation** (`src/generation/`)
   - `prompt.py` — strict grounding system prompt (English only, mandatory `[Spec, Section]` citations, exact refusal phrase when context is insufficient) and context formatter.
   - `generator.py` — `GeminiGenerator` using the unified `google-genai` SDK (`client.models.generate_content`, temperature 0.0, system instruction). Returns the refusal message immediately when no chunks are retrieved.

5. **Orchestration**
   - `src/pipeline.py` — `RAGPipeline` chains retrieval + generation and measures per-stage latency.
   - `src/app.py` — **FastAPI** backend: `POST /chat` (query → full RAG result with sources, routing and latencies) and `GET /health`. The pipeline is loaded lazily on first request; CORS is open for local development. Maps upstream errors to friendly HTTP statuses (429 quota, 503 overloaded).
   - `interface/` — **React + Vite** frontend: ChatGPT-style chat UI (light theme, robot avatar, Markdown-rendered answers, typing indicator, error messages).

---

## Project structure

```
rag-3gpp-5g/
├── main.py                     # Launches backend + frontend and opens the browser
├── config.yaml                 # Tunable parameters (chunking, retrieval, models)
├── requirements.txt
├── data/
│   ├── raw/                    # TS 23.501 / TS 24.501 .docx sources
│   ├── processed/              # parsed_blocks.json, chunks.json
│   └── index/                  # chroma_db/, bm25_index.pkl
├── src/
│   ├── app.py                  # FastAPI backend
│   ├── pipeline.py             # End-to-end RAG pipeline
│   ├── ingestion/              # parser.py, chunker.py, inspect/ utilities
│   ├── indexing/               # embedder.py, build_index.py
│   ├── retrieval/              # router, vector_search, bm25_search, hybrid, reranker
│   └── generation/             # generator.py, prompt.py
├── interface/                  # React + Vite chat UI
├── evaluation/                 # eval_dataset.json (33 questions), eval scripts, results/
└── tests/                      # pytest tests (chatbot, metrics, router)
```

---

## Installation

```bash
pip install -r requirements.txt
pip install google-genai fastapi uvicorn   # SDK + API deps

cd interface
npm install
cd ..
```

Create a `.env` file at the project root with your Gemini API key(s):

```
LLM_API_KEYS=key1,key2        # comma-separated keys enable automatic rotation
# or: LLM_API_KEY=... / GEMINI_API_KEY=...
```

## Building the knowledge base

```bash
# 1. Parse the .docx specifications into structured blocks
python src/ingestion/parser.py

# 2. Chunk the blocks (structural chunking, ~1000-1600 chars)
python src/ingestion/chunker.py

# 3. Build ChromaDB vector index + BM25 index
python src/indexing/build_index.py
```

## Running the application

**One command** (starts FastAPI on :8000, Vite on :5173, opens the browser):

```bash
python main.py
```

Or manually:

```bash
# Backend
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000

# Frontend
cd interface && npm run dev
```

Then open http://localhost:5173.

---

## Configuration

`config.yaml` centralizes tunable parameters without touching code:

- `chunking`: max/overlap sizes (defaults: 400 tokens / 40 tokens overlap)
- `embedding`: embedding model (`BAAI/bge-base-en-v1.5`)
- `retrieval`: candidate pool (30), final top-k (5), hybrid weights, router/reranker toggles, reranker model
- `generation`: refusal message

---

## Evaluation

`evaluation/` contains a 33-question dataset (`eval_dataset.json`) mixing in-corpus and out-of-corpus questions, plus three evaluation scripts:

| Script | Purpose |
|---|---|
| `eval_01_optimize_k.py` | Optimizes the retrieval top-k (Recall@k, MRR, section hit rate) |
| `eval_02_ablation.py` | Ablation study: router / reranker / hybrid on/off |
| `eval_03_generation.py` | End-to-end generation evaluation with RAGAS metrics (faithfulness, answer relevancy, answer correctness) + citation accuracy, refusal rates and latency |

Results and LLM/RAGAS caches are stored in `evaluation/results/` so runs can resume after quota interruptions. The winning configuration found by the ablation (no router, reranker on, K=15, pool=30) is documented at the top of `eval_03_generation.py`.

## Tests

```bash
pytest tests/
```

Covers the chatbot pipeline, retrieval metrics and the query router.

---

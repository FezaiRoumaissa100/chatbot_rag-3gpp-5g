"""Central configuration: built-in defaults < config.yaml."""
from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULTS: dict = {
    "corpus": {"raw_dir": "data/raw", "default_release": "18",
               "specs": ["TS 23.501", "TS 24.501", "TS 23.502", "TS 33.501"]},
    "chunking": {"target_chars": 1000, "max_chars": 1600, "overlap_chars": 350},
    "embedding": {
        "active": "bge-base", "max_seq_length": 512,
        "models": {
            "bge-base": {"hf_name": "BAAI/bge-base-en-v1.5",
                         "query_prefix": "Represent this sentence for searching relevant passages: ",
                         "doc_prefix": "", "multilingual": False},
            "bge-m3": {"hf_name": "BAAI/bge-m3", "query_prefix": "", "doc_prefix": "", "multilingual": True},
            "e5-base": {"hf_name": "intfloat/e5-base-v2", "query_prefix": "query: ",
                        "doc_prefix": "passage: ", "multilingual": False},
        },
    },
    "reranker": {"active": "minilm", "models": {
        "minilm": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "bge-base": "BAAI/bge-reranker-base",
        "bge-m3": "BAAI/bge-reranker-v2-m3"}},
    "retrieval": {"top_k": 15, "candidate_pool": 30, "mode": "hybrid", "routing": "soft",
                  "use_reranker": True, "vector_weight": 0.6, "bm25_weight": 0.4, "rrf_k": 60,
                  "soft_boost": 1.25, "coverage": True, "coverage_min_per_spec": 3,
                  "min_rerank_score": None},
    "generation": {"default_llm": "gemini:gemini-3.5-flash-lite",
                   "gemini_models": ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"],
                   "ollama_host": "http://localhost:11434", "ollama_num_ctx": 16384,
                   "refusal_message": "I could not find this information in the documents"},
}


def _merge(base: dict, over: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def load_config() -> dict:
    path = PROJECT_ROOT / "config.yaml"
    user = {}
    if path.exists() and yaml is not None:
        user = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _merge(DEFAULTS, user)


def cfg(section: str | None = None):
    c = load_config()
    return c if section is None else c[section]

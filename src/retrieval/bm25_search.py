import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.tokenizer import tokenize_3gpp

BM25_FILE = PROJECT_ROOT / "data" / "index" / "bm25_index.pkl"
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.json"


class BM25Searcher:
    """Lexical search over the serialized BM25Okapi index."""

    def __init__(self, bm25_file: Path = BM25_FILE, chunks_file: Path = CHUNKS_FILE):
        with open(bm25_file, "rb") as f:
            payload = pickle.load(f)
        self.bm25, self.chunk_ids = payload["bm25"], payload["chunk_ids"]
        chunks = json.loads(Path(chunks_file).read_text(encoding="utf-8"))
        self.chunk_map = {c["chunk_id"]: c for c in chunks}

    def corpus_info(self) -> list[dict]:
        seen: dict[tuple, int] = {}
        for c in self.chunk_map.values():
            k = (c["specification"], str(c["release"]), c.get("version", ""))
            seen[k] = seen.get(k, 0) + 1
        return [{"specification": s, "release": r, "version": v, "chunks": n}
                for (s, r, v), n in sorted(seen.items())]

    def search(self, query: str, top_k: int = 15, target_specs: list[str] | None = None,
               releases: list[str] | None = None) -> list[dict]:
        tokens = tokenize_3gpp(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        hits = []
        for idx in np.argsort(-scores):
            score = float(scores[idx])
            if score <= 0:
                break
            cid = self.chunk_ids[idx]
            c = self.chunk_map[cid]
            if target_specs and c["specification"] not in target_specs:
                continue
            if releases and str(c["release"]) not in releases:
                continue
            hits.append({
                "chunk_id": cid, "text": c["text"],
                "metadata": {"specification": c["specification"], "release": str(c["release"]),
                             "version": c.get("version", ""), "section": str(c["section"]),
                             "title": c["title"], "hierarchy": c["hierarchy"],
                             "has_table": bool(c["has_table"])},
                "bm25_score": round(score, 4), "bm25_rank": len(hits) + 1})
            if len(hits) >= top_k:
                break
        return hits

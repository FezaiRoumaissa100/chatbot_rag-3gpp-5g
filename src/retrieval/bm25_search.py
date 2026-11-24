import json
import pickle
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BM25_FILE = PROJECT_ROOT / "data" / "index" / "bm25_index.pkl"
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.json"


def tokenize_3gpp(text: str) -> list[str]:
    """3GPP-aware tokenizer matching the BM25 indexing pipeline."""
    return re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.lower())


class BM25Searcher:
    """Exact lexical search over serialized BM25Okapi index."""

    def __init__(self, bm25_file: Path = BM25_FILE, chunks_file: Path = CHUNKS_FILE):
        with open(bm25_file, "rb") as f:
            payload = pickle.load(f)

        self.bm25 = payload["bm25"]
        self.chunk_ids = payload["chunk_ids"]

        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks_list = json.load(f)

        self.chunk_map = {c["chunk_id"]: c for c in chunks_list}

    def search(
        self,
        query: str,
        top_k: int = 15,
        target_specs: list[str] | None = None,
    ) -> list[dict]:
        tokens = tokenize_3gpp(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)
        scored_indices = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        hits = []
        for idx, score in scored_indices:
            if score <= 0:
                break

            cid = self.chunk_ids[idx]
            chunk = self.chunk_map[cid]

            if target_specs and chunk["specification"] not in target_specs:
                continue

            hits.append({
                "chunk_id": cid,
                "text": chunk["text"],
                "metadata": {
                    "specification": chunk["specification"],
                    "release": str(chunk["release"]),
                    "section": str(chunk["section"]),
                    "title": chunk["title"],
                    "hierarchy": chunk["hierarchy"],
                    "has_table": bool(chunk["has_table"]),
                },
                "bm25_score": round(float(score), 4),
                "bm25_rank": len(hits) + 1,
            })

            if len(hits) >= top_k:
                break

        return hits
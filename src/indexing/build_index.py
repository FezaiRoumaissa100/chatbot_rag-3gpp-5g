"""Builds the vector indexes (one ChromaDB collection per embedding model) and the BM25 index.

    python -m src.indexing.build_index                 # active embedding from config.yaml
    python -m src.indexing.build_index --model bge-m3  # one specific model
    python -m src.indexing.build_index --all           # every model in config.yaml (comparison study)
"""
import argparse
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cfg
from src.indexing.embedder import TextEmbedder, collection_name
from src.retrieval.tokenizer import tokenize_3gpp

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.json"
INDEX_DIR = PROJECT_ROOT / "data" / "index"
CHROMA_DIR = INDEX_DIR / "chroma_db"
BM25_FILE = INDEX_DIR / "bm25_index.pkl"
BATCH = 64


def build_vector_index(chunks: list[dict], embedder: TextEmbedder):
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    name = collection_name(embedder.alias)
    try:
        client.delete_collection(name)
    except Exception:
        pass
    col = client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
    t0 = time.time()
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        col.add(
            ids=[c["chunk_id"] for c in batch],
            embeddings=embedder.encode_documents([c["text"] for c in batch], BATCH),
            documents=[c["text"] for c in batch],
            metadatas=[{"specification": c["specification"], "release": str(c["release"]),
                        "version": c.get("version", ""), "section": str(c["section"]),
                        "title": c["title"], "hierarchy": c["hierarchy"],
                        "has_table": bool(c["has_table"])} for c in batch],
        )
        if (i // BATCH) % 20 == 0 or i + BATCH >= len(chunks):
            print(f"  [{embedder.alias}] {min(i + BATCH, len(chunks))}/{len(chunks)} ({time.time()-t0:.0f}s)")
    return col


def build_bm25_index(chunks: list[dict]):
    print("Building BM25 index...")
    bm25 = BM25Okapi([tokenize_3gpp(c["text"]) for c in chunks])
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(BM25_FILE, "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": [c["chunk_id"] for c in chunks]}, f)
    print(f"  saved {BM25_FILE}")


def sanity_check(col, embedder: TextEmbedder):
    q = "What are the 5GMM states in 5GS?"
    r = col.query(query_embeddings=[embedder.encode_query(q)], n_results=3)
    print(f"  sanity '{q}'")
    for cid, m, d in zip(r["ids"][0], r["metadatas"][0], r["distances"][0]):
        print(f"    {m['specification']} Rel-{m['release']} §{m['section']} ({1-d:.3f}) {cid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", help="embedding alias (repeatable)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip-bm25", action="store_true")
    args = ap.parse_args()

    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    print(f"{len(chunks)} chunks:")
    for (s, r), n in sorted(Counter((c["specification"], c["release"]) for c in chunks).items()):
        print(f"  {s} Rel-{r}: {n}")

    aliases = list(cfg("embedding")["models"]) if args.all else (args.model or [cfg("embedding")["active"]])
    for alias in aliases:
        emb = TextEmbedder(alias)
        sanity_check(build_vector_index(chunks, emb), emb)
        del emb
    if not args.skip_bm25:
        build_bm25_index(chunks)
    print("\nIndexing finished.")


if __name__ == "__main__":
    main()

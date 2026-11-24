import json
import pickle
import re
import time
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

# Compatible whether run directly (`python src/indexing/indexer.py`) or as a module
try:
    from src.indexing.embedder import TextEmbedder
except ImportError:
    from embedder import TextEmbedder

# ============================================================
# 1. CONFIGURATION & PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.json"

INDEX_DIR = PROJECT_ROOT / "data" / "index"
CHROMA_DIR = INDEX_DIR / "chroma_db"
BM25_FILE = INDEX_DIR / "bm25_index.pkl"

COLLECTION_NAME = "3gpp_5g_specs"
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
BATCH_SIZE = 128


# ============================================================
# 2. TELECOM-AWARE TOKENIZER FOR BM25
# ============================================================

def tokenize_3gpp(text: str) -> list[str]:
    """
    Tokenizes text for BM25 while preserving hyphenated 3GPP identifiers
    (e.g., '5g-guti', 's-nssai', '5gmm-registered', 'ts 24.501').
    """
    return re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.lower())


# ============================================================
# 3. VECTOR INDEX BUILDER (CHROMADB)
# ============================================================

def build_vector_index(chunks: list[dict], embedder: TextEmbedder) -> chromadb.Collection:
    """Stores dense embeddings and metadata in a persistent ChromaDB collection."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"Existing collection '{COLLECTION_NAME}' cleared.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    total = len(chunks)
    print(f"\nIndexing {total} chunks into ChromaDB (batch size={BATCH_SIZE})...")
    start_time = time.time()

    for start_idx in range(0, total, BATCH_SIZE):
        end_idx = min(start_idx + BATCH_SIZE, total)
        batch = chunks[start_idx:end_idx]

        ids = [c["chunk_id"] for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = [
            {
                "specification": c["specification"],
                "release": str(c["release"]),
                "section": str(c["section"]),
                "title": c["title"],
                "hierarchy": c["hierarchy"],
                "has_table": bool(c["has_table"]),
            }
            for c in batch
        ]

        embeddings = embedder.encode_documents(texts, batch_size=BATCH_SIZE)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        if end_idx % (BATCH_SIZE * 5) == 0 or end_idx == total:
            elapsed = time.time() - start_time
            print(f"  Indexed {end_idx}/{total} chunks ({elapsed:.1f}s)")

    return collection


# ============================================================
# 4. SPARSE LEXICAL INDEX BUILDER (BM25)
# ============================================================

def build_bm25_index(chunks: list[dict]) -> BM25Okapi:
    """Builds and serializes a BM25Okapi lexical index aligned with chunk_ids."""
    print("\nBuilding BM25 lexical index...")
    start_time = time.time()

    chunk_ids = [c["chunk_id"] for c in chunks]
    tokenized_corpus = [tokenize_3gpp(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "bm25": bm25,
        "chunk_ids": chunk_ids,
    }

    with open(BM25_FILE, "wb") as f:
        pickle.dump(payload, f)

    elapsed = time.time() - start_time
    print(f"BM25 index saved to {BM25_FILE} ({elapsed:.1f}s)")
    return bm25


# ============================================================
# 5. SANITY CHECK & MAIN EXECUTION
# ============================================================

def run_sanity_check(collection: chromadb.Collection, embedder: TextEmbedder):
    """Runs a quick test query to verify vector retrieval."""
    print("\n" + "=" * 60)
    print("INDEX SANITY CHECK")
    print("=" * 60)

    test_query = "What are the 5GMM states in 5GS?"
    query_vec = embedder.encode_query(test_query)

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=3,
    )

    print(f"Test query: '{test_query}'\nTop 3 vector matches:")
    for rank, (cid, meta, dist) in enumerate(
        zip(results["ids"][0], results["metadatas"][0], results["distances"][0]),
        start=1,
    ):
        similarity = 1 - dist
        print(
            f"  {rank}. [{meta['specification']} | Sec {meta['section']} - {meta['title']}] "
            f"(id={cid}, score={similarity:.4f})"
        )


def main():
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(f"Chunks file not found: {CHUNKS_FILE}")

    print(f"Loading chunks from {CHUNKS_FILE}...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks.")

    embedder = TextEmbedder(model_name=EMBEDDING_MODEL_NAME)
    collection = build_vector_index(chunks, embedder)
    build_bm25_index(chunks)

    print("\n====================================================")
    print("INDEXING COMPLETED SUCCESSFULLY")
    print("====================================================")
    print(f"ChromaDB count : {collection.count()} vectors")
    print(f"ChromaDB path  : {CHROMA_DIR}")
    print(f"BM25 path      : {BM25_FILE}")

    run_sanity_check(collection, embedder)


if __name__ == "__main__":
    main()
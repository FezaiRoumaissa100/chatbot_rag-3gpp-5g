import sys
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.embedder import TextEmbedder, collection_name

CHROMA_DIR = PROJECT_ROOT / "data" / "index" / "chroma_db"


def build_where(specs: list[str] | None, releases: list[str] | None) -> dict | None:
    conds = []
    for key, vals in (("specification", specs), ("release", releases)):
        if vals:
            conds.append({key: vals[0]} if len(vals) == 1 else {key: {"$in": list(vals)}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


class VectorSearcher:
    """Dense search over the ChromaDB collection of one embedding model."""

    def __init__(self, embedding_alias: str | None = None, chroma_dir: Path = CHROMA_DIR,
                 embedder: TextEmbedder | None = None):
        self.embedder = embedder or TextEmbedder(embedding_alias)
        client = chromadb.PersistentClient(path=str(chroma_dir))
        name = collection_name(self.embedder.alias)
        try:
            self.collection = client.get_collection(name=name)
        except Exception as e:
            raise RuntimeError(
                f"Collection '{name}' not found. Build it with: "
                f"python -m src.indexing.build_index --model {self.embedder.alias}") from e

    def search(self, query: str, top_k: int = 15, target_specs: list[str] | None = None,
               releases: list[str] | None = None) -> list[dict]:
        res = self.collection.query(
            query_embeddings=[self.embedder.encode_query(query)],
            n_results=top_k, where=build_where(target_specs, releases))
        if not res["ids"] or not res["ids"][0]:
            return []
        hits = []
        for rank, (cid, doc, meta, dist) in enumerate(
                zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]), start=1):
            hits.append({"chunk_id": cid, "text": doc, "metadata": meta,
                         "vector_score": round(1.0 - float(dist), 4), "vector_rank": rank})
        return hits

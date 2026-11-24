import sys
from pathlib import Path
import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.embedder import TextEmbedder

CHROMA_DIR = PROJECT_ROOT / "data" / "index" / "chroma_db"
COLLECTION_NAME = "3gpp_5g_specs"


class VectorSearcher:
    """Dense semantic search over ChromaDB using local BGE embeddings."""

    def __init__(
        self,
        chroma_dir: Path = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        embedder: TextEmbedder | None = None,
    ):
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_collection(name=collection_name)
        self.embedder = embedder or TextEmbedder()

    def search(
        self,
        query: str,
        top_k: int = 15,
        target_specs: list[str] | None = None,
    ) -> list[dict]:
        query_vec = self.embedder.encode_query(query)

        where_filter = None
        if target_specs and len(target_specs) == 1:
            where_filter = {"specification": target_specs[0]}
        elif target_specs and len(target_specs) > 1:
            where_filter = {"specification": {"$in": target_specs}}

        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where_filter,
        )

        hits = []
        if not results["ids"] or not results["ids"][0]:
            return hits

        for rank, (cid, doc, meta, dist) in enumerate(
            zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ),
            start=1,
        ):
            hits.append({
                "chunk_id": cid,
                "text": doc,
                "metadata": meta,
                "vector_score": round(1.0 - float(dist), 4),
                "vector_rank": rank,
            })

        return hits
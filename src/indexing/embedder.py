from sentence_transformers import SentenceTransformer

from src.config import cfg


def collection_name(alias: str) -> str:
    return "3gpp_" + alias.replace("-", "_")


class TextEmbedder:
    """Registry-driven embedding wrapper (query/document prefixes differ per model family)."""

    def __init__(self, alias: str | None = None):
        conf = cfg("embedding")
        self.alias = alias or conf["active"]
        if self.alias not in conf["models"]:
            raise KeyError(f"Unknown embedding '{self.alias}'. Known: {list(conf['models'])}")
        spec = conf["models"][self.alias]
        self.model_name = spec["hf_name"]
        self.query_prefix = spec.get("query_prefix", "")
        self.doc_prefix = spec.get("doc_prefix", "")
        print(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.model.max_seq_length = conf.get("max_seq_length", 512)

    @property
    def collection(self) -> str:
        return collection_name(self.alias)

    def encode_documents(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        texts = [self.doc_prefix + t for t in texts]
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False,
                                 normalize_embeddings=True).tolist()

    def encode_query(self, query: str) -> list[float]:
        return self.model.encode([self.query_prefix + query], normalize_embeddings=True)[0].tolist()

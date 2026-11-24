import asyncio
import importlib
import json
import math
import os
import re
import sys
import time
import warnings
from pathlib import Path
import httpx
import numpy as np

# 1. Ajout de la racine du projet (rag-3gpp-5g) au PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 2. Lecture directe du fichier .env a la racine du projet
env_path = ROOT_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

warnings.filterwarnings("ignore", category=DeprecationWarning)

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from openai import AsyncOpenAI
from ragas import EvaluationDataset, RunConfig, SingleTurnSample, evaluate
from ragas.llms import llm_factory
from ragas.metrics import AnswerCorrectness, AnswerRelevancy, Faithfulness

try:
    from ragas.embeddings.base import BaseRagasEmbeddings
except ImportError:
    try:
        from ragas.embeddings import BaseRagasEmbeddings
    except ImportError:
        BaseRagasEmbeddings = object

# ==============================================================================
# CONFIGURATION DU PIPELINE GAGNANT (Issu de eval_02_ablation.py)
# ==============================================================================
GENERATOR_MODEL = "gemini-3.5-flash-lite"  # Modele utilise pour les 33 generations
JUDGE_MODEL = "gemini-3.1-flash-lite"      # Juge RAGAS
LOCAL_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

TOP_K = 15
CANDIDATE_POOL = 30                        # Pool RRF avant reranking vers Top-15
RAGAS_MAX_CHUNK_CHARS = 1500               # Garde les 15 chunks tout en limitant les tokens TPM
USE_ROUTER = False                         # Desactive : gain de Recall@15 mesure en ablation
USE_RERANKER = True                        # Active : ameliore le MRR
VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4
REQUEST_DELAY_S = 4.5                      # Pause anti-RPM lors de la generation

DATASET_PATH = ROOT_DIR / "evaluation" / "eval_dataset.json"
CACHE_PATH = ROOT_DIR / "evaluation" / "results" / "eval_03_generations_cache.json"
RAGAS_CACHE_PATH = ROOT_DIR / "evaluation" / "results" / "eval_03_ragas_cache.json"
OUTPUT_PATH = ROOT_DIR / "evaluation" / "results" / "eval_03_generation_results.json"

# Phrase de refus EXACTE exigee par l'enonce
REFUSAL_SENTENCE = "I could not find this information in the documents"

SYSTEM_PROMPT = f"""You are an expert in 3GPP 5G specifications (TS 23.501 and TS 24.501).
Answer the question ONLY from the specification excerpts provided in the context.

Strict rules:
1. Always answer in English, even if the question is in another language.
2. Never use outside knowledge. If the context does not explicitly contain the information needed, reply with exactly: "{REFUSAL_SENTENCE}" and nothing else.
3. Cite the specification and section for every technical claim, in this format: [TS 23.501, Section 5.2.1] or [TS 24.501, Section 5.5.1.2]."""


# ==============================================================================
# CLIENT HTTP REGULE POUR RAGAS (Timeout 60s + Rotation multi-cles)
# ==============================================================================
class RateLimitedGeminiHttpClient(httpx.AsyncClient):
    """Espace automatiquement les requetes RAGAS, coupe vite si bloque, et alterne les cles."""

    def __init__(self, keys: list[str], rpm_per_key: float = 12.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keys = keys
        self.min_interval = 60.0 / (rpm_per_key * max(len(keys), 1))
        self._lock = asyncio.Lock()
        self._last_call = 0.0
        self._key_idx = 0

    async def send(self, request: httpx.Request, *args, **kwargs) -> httpx.Response:
        await request.aread()
        response = None
        consecutive_429 = 0

        for attempt in range(1, 5):
            async with self._lock:
                now = time.monotonic()
                wait = self.min_interval - (now - self._last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                current_key = self.keys[self._key_idx % len(self.keys)]
                self._key_idx += 1
                self._last_call = time.monotonic()

            request.headers["authorization"] = f"Bearer {current_key}"
            try:
                response = await super().send(request, *args, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < 4:
                    await asyncio.sleep(2.0)
                    continue
                raise

            if response.status_code == 429:
                await response.aread()
                body = response.text

                # Quota JOURNALIER epuise : inutile de reessayer, on echoue tout de suite
                if "per day" in body.lower() or "perday" in body.lower():
                    raise RuntimeError("Quota journalier epuise : " + body[:200])

                consecutive_429 += 1
                if consecutive_429 < len(self.keys):
                    continue
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", body, re.IGNORECASE)
                sleep_s = float(match.group(1)) + 2.0 if match else 20.0
                await asyncio.sleep(min(sleep_s, 65.0))
                consecutive_429 = 0
                continue

            consecutive_429 = 0
            if response.status_code in (500, 502, 503, 504) and attempt < 4:
                await response.aread()
                await asyncio.sleep(min(3.0 * attempt, 15.0))
                continue

            return response
        return response


# ==============================================================================
# EMBEDDINGS LOCAUX POUR RAGAS (Compatible toutes versions RAGAS + run_config)
# ==============================================================================
class LocalBgeEmbeddings(BaseRagasEmbeddings):
    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL):
        if BaseRagasEmbeddings is not object:
            try:
                super().__init__()
            except TypeError:
                pass
        from sentence_transformers import SentenceTransformer

        self.run_config = RunConfig()
        self.model = SentenceTransformer(model_name)

    def set_run_config(self, run_config: RunConfig):
        self.run_config = run_config

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_text(self, text: str, **kwargs) -> list[float]:
        return self.embed_query(text)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_text(self, text: str, **kwargs) -> list[float]:
        return self.embed_query(text)


# ==============================================================================
# GESTIONNAIRE DE ROTATION DES CLES API (LLM_API_KEYS)
# ==============================================================================
class ApiKeyPool:
    def __init__(self, keys: list[str]):
        self.keys = [k.strip() for k in keys if k.strip()]
        if not self.keys:
            raise ValueError(f"Aucune cle API valide trouvee dans {env_path} (LLM_API_KEYS).")
        self.index = 0
        self.client = self._build_client(self.keys[self.index])

    def _build_client(self, api_key: str) -> genai.Client:
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_GENAI_API_KEY"] = api_key
        os.environ["GOOGLE_GENAI_API_VERSION"] = "v1beta"
        os.environ.pop("GOOGLE_API_KEY", None)
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta"),
        )

    def rotate(self) -> bool:
        if self.index + 1 < len(self.keys):
            self.index += 1
            self.client = self._build_client(self.keys[self.index])
            print(f"  -> Quota atteint : bascule automatique vers la cle API #{self.index + 1}/{len(self.keys)}")
            return True
        return False


def load_api_keys() -> list[str]:
    raw_multi = os.environ.get("LLM_API_KEYS", "")
    if raw_multi:
        return [k.strip() for k in raw_multi.split(",") if k.strip()]
    single = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    return [single] if single else []


# ==============================================================================
# FONCTIONS UTILITAIRES (Extraction chunks, Generation, Citations & Refus)
# ==============================================================================
def safe_round(val, digits: int = 3):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return round(float(val), digits)


def safe_nanmean(values: list) -> float | None:
    clean = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return safe_round(np.mean(clean)) if clean else None


def is_valid_ragas_entry(entry: dict | None) -> bool:
    """Verifie que les 3 metriques RAGAS d'une question ont bien ete calculees sans erreur."""
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("faithfulness") is not None
        and entry.get("answer_relevancy") is not None
        and entry.get("answer_correctness") is not None
    )


def extract_chunk_fields(chunk: dict) -> tuple[str, str, str]:
    meta = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else chunk
    spec = (
        meta.get("specification")
        or meta.get("spec")
        or meta.get("doc")
        or meta.get("source")
        or "Unknown Spec"
    )
    section = (
        meta.get("section")
        or meta.get("section_id")
        or meta.get("clause")
        or "Unknown Section"
    )
    text = chunk.get("text") or chunk.get("content") or chunk.get("chunk_text") or ""
    return str(spec), str(section), str(text)


def format_context(chunks: list[dict]) -> str:
    formatted = []
    for idx, chunk in enumerate(chunks, 1):
        spec, section, text = extract_chunk_fields(chunk)
        formatted.append(f"[Chunk {idx} | {spec} | Section {section}]\n{text}")
    return "\n\n---\n\n".join(formatted)


def generate_answer(key_pool: ApiKeyPool, query: str, chunks: list[dict]) -> tuple[str, float]:
    context_str = format_context(chunks)
    user_prompt = f"SPECIFICATION CONTEXT:\n{context_str}\n\nQUESTION:\n{query}"

    max_attempts = 20
    for attempt in range(1, max_attempts + 1):
        try:
            t0 = time.perf_counter()
            response = key_pool.client.models.generate_content(
                model=GENERATOR_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                ),
            )
            gen_latency = time.perf_counter() - t0
            return (response.text or "").strip(), gen_latency

        except genai_errors.ClientError as e:
            if e.code == 429:
                msg = str(e)
                if "PerMinute" in msg:
                    print("  -> Limite par minute (RPM) atteinte, pause de 35s...")
                    time.sleep(35)
                    continue
                if key_pool.rotate():
                    continue
                raise RuntimeError("Toutes les cles API de LLM_API_KEYS ont atteint leur quota.") from e
            raise

        except genai_errors.ServerError as e:
            if e.code in (500, 502, 503, 504) and attempt < max_attempts:
                wait_s = min(10 * attempt, 45)
                print(
                    f"  -> Serveur Google surcharge (HTTP {e.code}, essai {attempt}/{max_attempts}), "
                    f"nouvel essai dans {wait_s}s..."
                )
                time.sleep(wait_s)
                continue
            raise

    raise RuntimeError("Echec de generation apres plusieurs tentatives.")


def check_refusal(answer: str) -> bool:
    """Un refus = la phrase exacte exigee par l'enonce apparait dans la reponse."""
    return REFUSAL_SENTENCE.lower() in answer.lower()


def evaluate_citations(answer: str, retrieved_chunks: list[dict]) -> float:
    cited_pairs = re.findall(
        r"(TS\s*2[34]\.501)[^\d]{0,15}(\d+(?:\.\d+)+)", answer, flags=re.IGNORECASE
    )
    if not cited_pairs:
        return 0.0

    valid_sources = set()
    for ch in retrieved_chunks:
        spec, sec, _ = extract_chunk_fields(ch)
        norm_spec = re.sub(r"\s+", " ", spec.upper()).strip()
        norm_sec = sec.strip()
        if norm_spec and norm_sec:
            valid_sources.add((norm_spec, norm_sec))

    valid_count = 0
    for raw_spec, raw_sec in cited_pairs:
        norm_spec = re.sub(r"\s+", " ", raw_spec.upper()).strip()
        is_valid = any(
            norm_spec == v_spec
            and (
                raw_sec == v_sec
                or v_sec.startswith(raw_sec + ".")
                or raw_sec.startswith(v_sec + ".")
            )
            for v_spec, v_sec in valid_sources
        )
        if is_valid:
            valid_count += 1

    return valid_count / len(cited_pairs)


def load_hybrid_retriever_class():
    for py_file in ROOT_DIR.rglob("*.py"):
        if any(p in {"venv", ".venv", "env", "__pycache__", "evaluation"} for p in py_file.parts):
            continue
        if "class HybridRetriever" in py_file.read_text(encoding="utf-8", errors="ignore"):
            module_name = ".".join(py_file.relative_to(ROOT_DIR).with_suffix("").parts)
            return getattr(importlib.import_module(module_name), "HybridRetriever")
    raise ImportError("Fichier contenant 'class HybridRetriever' introuvable dans le projet.")


def load_json_file(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json_file(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==============================================================================
# EXECUTION DE L'EVALUATION COMPLETE
# ==============================================================================
def main():
    keys = load_api_keys()
    key_pool = ApiKeyPool(keys)
    print(f"{len(key_pool.keys)} cle(s) API chargee(s).")

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cache = load_json_file(CACHE_PATH)
    ragas_cache = load_json_file(RAGAS_CACHE_PATH)
    retriever = None

    in_corpus_items = []
    out_of_corpus_records = []

    print(
        f"Lancement de l'evaluation sur {len(dataset)} questions "
        f"(Gen={GENERATOR_MODEL}, Judge={JUDGE_MODEL}, K={TOP_K}, Pool={CANDIDATE_POOL}, "
        f"Router={USE_ROUTER}, Reranker={USE_RERANKER})...\n"
    )

    for idx, item in enumerate(dataset, 1):
        q_id = str(item.get("id", idx))
        query = item.get("question") or item.get("query")
        ground_truth = (
            item.get("ground_truth")
            or item.get("reference_answer")
            or item.get("expected_answer", "")
        )
        expected_sections = item.get("expected_sections", [])
        is_in_corpus = len(expected_sections) > 0

        if q_id in cache:
            cached = cache[q_id]
            record = cached["record"]
            retrieved_texts = cached["retrieved_texts"]
            source_tag = "CACHE"
        else:
            if retriever is None:
                HybridRetriever = load_hybrid_retriever_class()
                retriever = HybridRetriever(
                    use_router=USE_ROUTER,
                    use_reranker=USE_RERANKER,
                    vector_weight=VECTOR_WEIGHT,
                    bm25_weight=BM25_WEIGHT,
                )

            t_ret_start = time.perf_counter()
            retrieval_out = retriever.retrieve(
                query=query,
                top_k=TOP_K,
                candidate_pool=CANDIDATE_POOL,
            )
            ret_latency = time.perf_counter() - t_ret_start
            chunks = retrieval_out["results"]

            answer, gen_latency = generate_answer(key_pool, query, chunks)
            total_latency = ret_latency + gen_latency
            refused = check_refusal(answer)
            retrieved_texts = [extract_chunk_fields(c)[2] for c in chunks]

            record = {
                "id": item.get("id", idx),
                "question": query,
                "is_in_corpus": is_in_corpus,
                "expected_sections": expected_sections,
                "answer": answer,
                "ground_truth": ground_truth,
                "refused": refused,
                "retrieval_latency_s": round(ret_latency, 3),
                "generation_latency_s": round(gen_latency, 3),
                "total_latency_s": round(total_latency, 3),
            }
            if is_in_corpus:
                record["citation_accuracy"] = round(evaluate_citations(answer, chunks), 3)

            cache[q_id] = {"record": record, "retrieved_texts": retrieved_texts}
            save_json_file(CACHE_PATH, cache)
            source_tag = f"Cle#{key_pool.index + 1}"
            time.sleep(REQUEST_DELAY_S)

        if is_in_corpus:
            compact_contexts = [t[:RAGAS_MAX_CHUNK_CHARS] for t in retrieved_texts]
            sample = SingleTurnSample(
                user_input=query,
                retrieved_contexts=compact_contexts,
                response=record["answer"],
                reference=ground_truth,
            )
            in_corpus_items.append((q_id, record, sample))
        else:
            out_of_corpus_records.append(record)

        print(
            f"[{idx}/{len(dataset)}] [{source_tag}] {'IN-CORPUS' if is_in_corpus else 'HORS-CORPUS'} | "
            f"Refus={record['refused']} | Latence={record['total_latency_s']:.2f}s"
        )

    # 3. Calcul des metriques RAGAS (reprend uniquement les questions non valides)
    pending = [
        (q_id, rec, smp)
        for (q_id, rec, smp) in in_corpus_items
        if not is_valid_ragas_entry(ragas_cache.get(q_id))
    ]
    print(
        f"\nCalcul des metriques RAGAS ({len(in_corpus_items) - len(pending)} valides en cache, "
        f"{len(pending)} restantes) avec {JUDGE_MODEL}..."
    )

    if pending:
        gemini_openai_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        judge_embeddings = LocalBgeEmbeddings(LOCAL_EMBEDDING_MODEL)
        # Peu de reessais et timeout court : on echoue vite au lieu de bloquer pendant des minutes
        run_config = RunConfig(max_workers=1, max_retries=1, timeout=120)

        batch_size = 10
        for b_start in range(0, len(pending), batch_size):
            batch = pending[b_start : b_start + batch_size]
            print(
                f"\n--- Lot RAGAS {b_start // batch_size + 1}/"
                f"{(len(pending) + batch_size - 1) // batch_size} ({len(batch)} questions) ---"
            )

            # Client HTTP neuf pour chaque lot (evite APIConnectionError apres fermeture par RAGAS)
            rate_limited_http = RateLimitedGeminiHttpClient(keys=key_pool.keys, rpm_per_key=12.0, timeout=60.0)
            judge_async_client = AsyncOpenAI(
                api_key=key_pool.keys[0],
                base_url=gemini_openai_url,
                http_client=rate_limited_http,
                max_retries=0,
            )
            judge_llm = llm_factory(
                JUDGE_MODEL,
                provider="openai",
                client=judge_async_client,
                max_tokens=2048,
            )
            ragas_metrics = [
                Faithfulness(llm=judge_llm),
                AnswerRelevancy(llm=judge_llm, embeddings=judge_embeddings, strictness=1),
                AnswerCorrectness(llm=judge_llm, embeddings=judge_embeddings),
            ]

            ds_batch = EvaluationDataset(samples=[x[2] for x in batch])
            res_batch = evaluate(dataset=ds_batch, metrics=ragas_metrics, run_config=run_config)
            df_batch = res_batch.to_pandas()

            batch_scores = []
            for i, (q_id, _, _) in enumerate(batch):
                scores = {
                    "faithfulness": safe_round(df_batch.loc[i, "faithfulness"]),
                    "answer_relevancy": safe_round(df_batch.loc[i, "answer_relevancy"]),
                    "answer_correctness": safe_round(df_batch.loc[i, "answer_correctness"]),
                }
                batch_scores.append(scores)
                ragas_cache[q_id] = scores
            save_json_file(RAGAS_CACHE_PATH, ragas_cache)

            # Arret de securite : si TOUT le lot a echoue, inutile de gaspiller le quota
            if all(v is None for s in batch_scores for v in s.values()):
                print(
                    "\nTout le lot RAGAS a echoue (quota epuise ou API indisponible). "
                    "Arret pour economiser le quota. Relance plus tard : les caches reprennent la ou ca s'est arrete."
                )
                sys.exit(1)

    in_corpus_records = []
    for q_id, rec, _ in in_corpus_items:
        scores = ragas_cache.get(q_id, {})
        rec["faithfulness"] = scores.get("faithfulness")
        rec["answer_relevancy"] = scores.get("answer_relevancy")
        rec["answer_correctness"] = scores.get("answer_correctness")
        in_corpus_records.append(rec)

    # 4. Agregation des metriques globales
    all_records = in_corpus_records + out_of_corpus_records
    summary = {
        "configuration": {
            "generator_model": GENERATOR_MODEL,
            "judge_model": JUDGE_MODEL,
            "embedding_model": LOCAL_EMBEDDING_MODEL,
            "top_k": TOP_K,
            "candidate_pool": CANDIDATE_POOL,
            "ragas_eval_top_k_contexts": TOP_K,
            "ragas_eval_max_chunk_chars": RAGAS_MAX_CHUNK_CHARS,
            "use_router": USE_ROUTER,
            "use_reranker": USE_RERANKER,
            "vector_weight": VECTOR_WEIGHT,
            "bm25_weight": BM25_WEIGHT,
        },
        "metrics": {
            "faithfulness_ragas": safe_nanmean([r["faithfulness"] for r in in_corpus_records]),
            "answer_relevancy_ragas": safe_nanmean([r["answer_relevancy"] for r in in_corpus_records]),
            "answer_correctness_ragas": safe_nanmean([r["answer_correctness"] for r in in_corpus_records]),
            "citation_accuracy": safe_round(np.mean([r["citation_accuracy"] for r in in_corpus_records])),
            "false_refusal_rate": safe_round(np.mean([1.0 if r["refused"] else 0.0 for r in in_corpus_records])),
            "true_refusal_rate": (
                safe_round(np.mean([1.0 if r["refused"] else 0.0 for r in out_of_corpus_records]))
                if out_of_corpus_records else None
            ),
            "avg_retrieval_latency_s": safe_round(np.mean([r["retrieval_latency_s"] for r in all_records])),
            "avg_generation_latency_s": safe_round(np.mean([r["generation_latency_s"] for r in all_records])),
            "avg_total_latency_s": safe_round(np.mean([r["total_latency_s"] for r in all_records])),
        },
        "in_corpus_details": in_corpus_records,
        "out_of_corpus_details": out_of_corpus_records,
    }

    save_json_file(OUTPUT_PATH, summary)

    print("\n" + "=" * 65)
    print(f"TABLEAU FINAL D'EVALUATION DE LA GENERATION ({GENERATOR_MODEL.upper()})")
    print("=" * 65)
    for k, v in summary["metrics"].items():
        print(f"{k:<30} : {v}")
    print("=" * 65)
    print(f"Rapport detaille sauvegarde dans : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
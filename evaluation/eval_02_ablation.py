import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.hybrid import HybridRetriever

DATASET_PATH = PROJECT_ROOT / "evaluation" / "eval_dataset.json"
RESULTS_PATH = PROJECT_ROOT / "evaluation" / "results" / "ablation_results.json"

def calculate_metrics(retrieved_chunks, expected_sections):
    if not expected_sections:
        return 1.0, 0.0

    expected_set = {(ex["specification"], ex["section"]) for ex in expected_sections}
    found_expected = set()
    first_hit_rank = 0

    for rank, chunk in enumerate(retrieved_chunks, start=1):
        chunk_spec = chunk["metadata"]["specification"]
        chunk_sec = chunk["metadata"]["section"]

        for exp_spec, exp_sec in expected_set:
            if chunk_spec == exp_spec and (chunk_sec == exp_sec or chunk_sec.startswith(exp_sec + ".")):
                found_expected.add((exp_spec, exp_sec))
                if first_hit_rank == 0:
                    first_hit_rank = rank

    recall = len(found_expected) / len(expected_set)
    mrr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
    return recall, mrr

def main():
    print("ETUDE D'ABLATION LEAVE-ONE-OUT - COMPARAISON DES ARCHITECTURES (K=15)")
    
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    corpus_questions = [q for q in dataset if q["expected_sections"]]
    
    configs = {
        "0. Baseline (Pipeline Complet)": {"use_router": True, "use_reranker": True, "vector_weight": 0.6, "bm25_weight": 0.4},
        "1. Ablation Routeur (Sans Routeur)": {"use_router": False, "use_reranker": True, "vector_weight": 0.6, "bm25_weight": 0.4},
        "2. Ablation Reranker (Sans Reranker)": {"use_router": True, "use_reranker": False, "vector_weight": 0.6, "bm25_weight": 0.4},
        "3. Ablation Hybride (Vectoriel seul)": {"use_router": True, "use_reranker": True, "vector_weight": 1.0, "bm25_weight": 0.0},
        "4. Ablation Hybride (Lexical seul)": {"use_router": True, "use_reranker": True, "vector_weight": 0.0, "bm25_weight": 1.0},
    }

    summary_results = []

    for name, kwargs in configs.items():
        print(f"\n--- Test de l'architecture : {name} ---")
        retriever = HybridRetriever(**kwargs)
        total_recall, total_mrr, total_time = 0.0, 0.0, 0.0
        
        for item in corpus_questions:
            query = item.get("question", item.get("query"))
            
            start_time = time.time()
            res = retriever.retrieve(query, top_k=15)
            latency = time.time() - start_time
            
            recall, mrr = calculate_metrics(res["results"], item["expected_sections"])
            
            total_recall += recall
            total_mrr += mrr
            total_time += latency
            
        avg_recall = total_recall / len(corpus_questions)
        avg_mrr = total_mrr / len(corpus_questions)
        avg_time = total_time / len(corpus_questions)
        
        summary_results.append({
            "Architecture": name,
            "Recall@15": avg_recall,
            "MRR": avg_mrr,
            "Latence": avg_time
        })
        
        print(f"Resultat -> Recall: {avg_recall:.3f} | MRR: {avg_mrr:.3f} | Latence: {avg_time:.3f}s")

    print("\nTABLEAU COMPARATIF FINAL DES ARCHITECTURES")
    print("| Architecture | Recall@15 | MRR | Latence moyenne |")
    print("| :--- | :--- | :--- | :--- |")
    for res in summary_results:
        print(f"| {res['Architecture']} | {res['Recall@15']:.3f} | {res['MRR']:.3f} | {res['Latence']:.3f} s |")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(summary_results, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
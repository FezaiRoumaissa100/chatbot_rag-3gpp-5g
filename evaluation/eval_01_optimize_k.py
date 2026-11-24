import json
import time
import sys
from pathlib import Path

# Ajout de la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.hybrid import HybridRetriever

DATASET_PATH = PROJECT_ROOT / "evaluation" / "eval_dataset.json"
RESULTS_PATH = PROJECT_ROOT / "results" / "optimization_k_results.json"

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
    print("OPTIMISATION DE K (5, 10, 15) SUR LE PIPELINE HYBRIDE COMPLET")
    
    # Chargement du jeu de donnees (uniquement les questions du corpus)
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    corpus_questions = [q for q in dataset if q["expected_sections"]]
    
    # Initialisation du retriever complet (Hybride + Routeur + Reranker)
    retriever = HybridRetriever(
        use_router=True,
        use_reranker=True,
        vector_weight=0.6,
        bm25_weight=0.4
    )

    k_values = [5, 10, 15]
    summary_results = []

    for k in k_values:
        print(f"\n--- Evaluation avec K = {k} ---")
        total_recall, total_mrr, total_time = 0.0, 0.0, 0.0
        
        for item in corpus_questions:
            query = item.get("question", item.get("query"))
            
            start_time = time.time()
            res = retriever.retrieve(query, top_k=k)
            latency = time.time() - start_time
            
            recall, mrr = calculate_metrics(res["results"], item["expected_sections"])
            
            total_recall += recall
            total_mrr += mrr
            total_time += latency
            
        avg_recall = total_recall / len(corpus_questions)
        avg_mrr = total_mrr / len(corpus_questions)
        avg_time = total_time / len(corpus_questions)
        
        summary_results.append({
            "k": k,
            "recall": avg_recall,
            "mrr": avg_mrr,
            "latency_sec": avg_time
        })
        
        print(f"Resultat K={k} -> Recall: {avg_recall:.3f} | MRR: {avg_mrr:.3f} | Latence: {avg_time:.3f}s")

    # Affichage du tableau final
    print("\nTABLEAU COMPARATIF FINAL")
    print("| Valeur de K | Recall@K | MRR | Latence moyenne |")
    print("| :--- | :--- | :--- | :--- |")
    for res in summary_results:
        print(f"| K={res['k']} | {res['recall']:.3f} | {res['mrr']:.3f} | {res['latency_sec']:.3f} s |")

    # Sauvegarde des resultats
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(summary_results, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import RAGPipeline


def main():
    query = "Describe the  registration procedure and the NAS messages exchanged between the UE and the AMF"

    pipeline = RAGPipeline(
        use_router=True,
        use_reranker=True,
        model_name="gemini-2.5-flash",
        top_k=10,

    )

    result = pipeline.run(query)

    print("=" * 90)
    print(f"QUESTION : {result['query']}")
    print("=" * 90)

    print(f"\n[1. CHUNKS FINAUX RETENUS ({len(result['sources'])})]\n")
    for rank, chunk in enumerate(result["sources"], start=1):
        meta = chunk["metadata"]
        print("-" * 90)
        print(
            f"Chunk #{rank} | Spécification : {meta['specification']} | "
            f"Section : {meta['section']} ({meta['title']})"
        )
        print("-" * 90)
        print(chunk["text"])
        print()

    print("=" * 90)
    print(f"[2. RÉPONSE FINALE DU CHATBOT] (Temps total : {result['latency_ms']['total']} ms)")
    print("=" * 90)
    print(result["answer"])
    print("=" * 90)


if __name__ == "__main__":
    main()
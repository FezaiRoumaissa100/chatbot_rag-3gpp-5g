import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.router import QueryRouter


TEST_CASES = [
    # (Catégorie, Question, target_specs attendu, confidence attendue)
    (
        "Cross-spec (AMF + NAS)",
        "Describe the registration procedure and the NAS messages exchanged between the UE and the AMF",
        None,
        "cross_spec",
    ),
    (
        "Explicite TS 23.501",
        "According to TS 23.501, what are the roles of SMF and UPF?",
        ["TS 23.501"],
        "explicit",
    ),
    (
        "Explicite TS 24.501",
        "Check TS 24.501 for 5GMM cause values.",
        ["TS 24.501"],
        "explicit",
    ),
    (
        "Implicite TS 23.501 (SBA/QoS)",
        "How does the NRF discover network functions in Service-Based Architecture using 5QI?",
        ["TS 23.501"],
        "high",
    ),
    (
        "Implicite TS 24.501 (Timer/Cause)",
        "What happens when timer T3510 expires and the UE receives Cause #9?",
        ["TS 24.501"],
        "high",
    ),
    (
        "Générale / Ambiguë",
        "How does a 5G mobile device connect to the network?",
        None,
        "cross_spec",
    ),
    (
        "Hors-sujet",
        "What is the best recipe for chocolate cake?",
        None,
        "cross_spec",
    ),
]


def main():
    router = QueryRouter()

    print("=" * 100)
    print("DIAGNOSTIC DU ROUTEUR 3GPP (QueryRouter)")
    print("=" * 100)

    passed = 0
    for category, query, expected_specs, expected_conf in TEST_CASES:
        decision = router.route(query)
        ok = (decision.target_specs == expected_specs) and (decision.confidence == expected_conf)
        status = "OK" if ok else "ÉCHEC"
        if ok:
            passed += 1

        print(f"\n[{status}] {category}")
        print(f"  Question   : {query}")
        print(f"  Résultat   : target_specs={decision.target_specs} | confidence={decision.confidence}")
        print(f"  Raison     : {decision.reason}")
        if not ok:
            print(f"  Attendu    : target_specs={expected_specs} | confidence={expected_conf}")

    print("\n" + "=" * 100)
    print(f"BILAN : {passed}/{len(TEST_CASES)} cas conformes")
    print("=" * 100)


if __name__ == "__main__":
    main()
| Configuration | N | Recall@15 | Full hit | MRR | Latency (s) | Unreachable | By category |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Full pipeline (soft routing + coverage) | 30 | 0.783 | 0.700 | 0.628 | 0.65 | 0/40 | cross_spec=0.55, single_23501=0.90, single_24501=0.90 |
| Hard routing (legacy) | 30 | 0.767 | 0.667 | 0.653 | 0.16 | 0/40 | cross_spec=0.50, single_23501=0.90, single_24501=0.90 |
| No routing | 30 | 0.800 | 0.733 | 0.628 | 0.16 | 0/40 | cross_spec=0.60, single_23501=0.90, single_24501=0.90 |
| No reranker | 30 | 0.833 | 0.767 | 0.688 | 0.07 | 0/40 | cross_spec=0.60, single_23501=0.90, single_24501=1.00 |
| Vector only | 30 | 0.800 | 0.733 | 0.628 | 0.15 | 0/40 | cross_spec=0.60, single_23501=0.90, single_24501=0.90 |
| BM25 only | 30 | 0.733 | 0.633 | 0.598 | 0.12 | 0/40 | cross_spec=0.50, single_23501=0.90, single_24501=0.80 |
| No coverage guarantee | 30 | 0.783 | 0.700 | 0.628 | 0.17 | 0/40 | cross_spec=0.55, single_23501=0.90, single_24501=0.90 |
| Candidate pool = 15 (legacy) | 30 | 0.800 | 0.733 | 0.625 | 0.11 | 0/40 | cross_spec=0.60, single_23501=0.90, single_24501=0.90 |
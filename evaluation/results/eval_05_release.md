| Configuration | N | Recall@15 | Full hit | MRR | Latency (s) | By category |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Core questions | default release filter (Rel-18) | 30 | 0.000 | 0.000 | 0.000 | 0.16 | cross_spec=0.00, single_23501=0.00, single_24501=0.00 |
| Core questions | NO release filter | 30 | 0.383 | 0.300 | 0.369 | 0.17 | cross_spec=0.25, single_23501=0.90, single_24501=0.00 |
| Release questions | release-aware routing | 6 | 0.500 | 0.333 | 0.556 | 0.27 | release_17=0.67, release_compare=0.33 |
| Release questions | release-blind (always Rel-18) | 6 | 0.000 | 0.000 | 0.000 | 0.17 | release_17=0.00, release_compare=0.00 |
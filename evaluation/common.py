"""Shared evaluation helpers (pure Python: unit-tested in tests/test_metrics.py)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generation.citations import validate_citations  # noqa: E402

RESULTS_DIR = ROOT / "evaluation" / "results"
BASE_SPECS = ["TS 23.501", "TS 24.501"]                       # the two specs of the original assignment
ALL_SPECS = BASE_SPECS + ["TS 23.502", "TS 33.501"]
REFUSAL_SENTENCE = "I could not find this information in the documents"


def load_dataset(path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def question_of(item: dict) -> str:
    return item.get("question") or item.get("query")


def _key(exp: dict) -> tuple:
    return (exp["specification"], exp["section"], exp.get("release"))


def retrieval_metrics(chunks: list[dict], expected: list[dict]) -> tuple[float, float]:
    """Recall = share of expected (spec, section[, release]) found; MRR from the first hit.
    A chunk matches when its section equals the expected one or is a sub-section of it."""
    if not expected:
        return 1.0, 0.0
    found, first = set(), 0
    for rank, ch in enumerate(chunks, 1):
        for exp in expected:
            m = ch["metadata"]
            ok = (m["specification"] == exp["specification"]
                  and (not exp.get("release") or str(m.get("release")) == str(exp["release"]))
                  and (m["section"] == exp["section"] or m["section"].startswith(exp["section"] + ".")))
            if ok:
                found.add(_key(exp))
                first = first or rank
    return len(found) / len({_key(e) for e in expected}), (1.0 / first if first else 0.0)


def is_refusal(answer: str) -> bool:
    return REFUSAL_SENTENCE.lower() in (answer or "").lower()


def citation_scores(answer: str, chunks: list[dict]) -> dict:
    v = validate_citations(answer, chunks)
    return {"citation_accuracy": v["accuracy"] if v["total"] else 0.0, "has_citation": v["total"] > 0,
            "n_citations": v["total"]}


def md_table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(":---" for _ in cols) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)

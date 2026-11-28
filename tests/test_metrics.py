"""Tests of the retrieval metrics and the spec-coverage selection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import is_refusal, retrieval_metrics
from src.retrieval.selection import balance_specs


def ch(spec, sec, rel="18"):
    return {"metadata": {"specification": spec, "section": sec, "release": rel}}


def test_recall_and_mrr_with_subsections():
    chunks = [ch("TS 24.501", "5.5.1.2"), ch("TS 23.501", "6.2.1.1")]
    r, m = retrieval_metrics(chunks, [{"specification": "TS 23.501", "section": "6.2.1"},
                                      {"specification": "TS 24.501", "section": "5.5.1"}])
    assert r == 1.0 and m == 1.0


def test_release_aware_expected_section():
    chunks = [ch("TS 23.501", "6.2.1", "18")]
    exp = [{"specification": "TS 23.501", "section": "6.2.1", "release": "17"},
           {"specification": "TS 23.501", "section": "6.2.1", "release": "18"}]
    assert retrieval_metrics(chunks, exp)[0] == 0.5


def test_refusal_detection():
    assert is_refusal("I could not find this information in the documents.")
    assert not is_refusal("The AMF terminates N1.")


def test_coverage_brings_missing_spec_into_top_k():
    ranked = [{"metadata": {"specification": "TS 23.501"}, "i": i} for i in range(10)] + \
             [{"metadata": {"specification": "TS 24.501"}, "i": 100 + i} for i in range(4)]
    out = balance_specs(ranked, ["TS 23.501", "TS 24.501"], 6, 3)
    assert sum(c["metadata"]["specification"] == "TS 24.501" for c in out) == 3 and len(out) == 6

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.generation.citations import extract_citations, validate_citations

CH = [{"metadata": {"specification": "TS 23.501", "release": "18", "section": "6.2.1"}},
      {"metadata": {"specification": "TS 24.501", "release": "17", "section": "5.5.1.2.1"}}]


def test_extract_with_and_without_release():
    c = extract_citations("A [TS 23.501, Section 6.2.1]. B [TS 24.501 Rel-17, Section 5.5.1.2].")
    assert [(x["specification"], x["release"], x["section"]) for x in c] == [
        ("TS 23.501", None, "6.2.1"), ("TS 24.501", "17", "5.5.1.2")]


def test_validation_uses_prefix_and_release():
    v = validate_citations("[TS 23.501, Section 6.2.1] [TS 24.501 Rel-17, Section 5.5.1.2] "
                           "[TS 24.501 Rel-18, Section 5.5.1.2] [TS 33.501, Section 6.1]", CH)
    assert [i["valid"] for i in v["items"]] == [True, True, False, False]


def test_no_citation_gives_none_accuracy():
    assert validate_citations("nothing", CH)["accuracy"] is None

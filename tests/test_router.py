import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval.router import QueryRouter

R = QueryRouter()


def test_explicit_spec_is_hard_filter():
    d = R.route("According to TS 23.501, what are the roles of SMF and UPF?")
    assert d.target_specs == ["TS 23.501"] and d.confidence == "explicit"


def test_nas_cues_prefer_24501():
    d = R.route("What happens when timer T3510 expires and the UE receives Cause #9?")
    assert d.target_specs == ["TS 24.501"] and d.confidence == "high"


def test_security_cues_prefer_33501():
    d = R.route("How does 5G AKA work and what is SUCI?")
    assert d.preferred_specs == ["TS 33.501"]


def test_cross_spec_has_several_preferred_and_no_hard_filter():
    d = R.route("Describe the registration procedure and the NAS messages exchanged between the UE and the AMF")
    assert d.target_specs is None and {"TS 23.501", "TS 24.501"} <= set(d.preferred_specs)


def test_off_topic_has_no_preference():
    d = R.route("What is the best recipe for chocolate cake?")
    assert d.target_specs is None and d.preferred_specs == []


def test_release_detection():
    assert R.route("In Rel-17, what are the SSC modes?").releases == ["17"]
    d = R.route("Compare the AMF functions between Release 17 and Release 18")
    assert d.compare and d.releases == ["17", "18"]
    assert not R.route("What is the difference between SSC mode 2 and 3?").compare

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval.query_processor import QueryProcessor, detect_language, expand_acronyms, is_smalltalk


class FakeLLM:
    calls = 0

    def generate(self, system, user, temperature=0.0):
        FakeLLM.calls += 1
        return 'Standalone question: "What does cause #9 mean in 5GMM?"'


def test_language_detection():
    assert detect_language("Que signifie la cause n°9 en 5GMM ?") == "fr"
    assert detect_language("What does cause #9 mean in 5GMM?") == "en"


def test_english_standalone_question_costs_no_llm_call():
    FakeLLM.calls = 0
    p = QueryProcessor(FakeLLM()).process("Describe the registration procedure and the NAS messages exchanged between the UE and the AMF")
    assert FakeLLM.calls == 0 and not p.rewritten


def test_french_is_translated_and_followup_is_condensed():
    qp = QueryProcessor(FakeLLM())
    assert qp.process("Que signifie la cause n°9 en 5GMM ?").english == "What does cause #9 mean in 5GMM?"
    assert qp.process("and T3511?", [{"role": "user", "content": "x"}]).rewritten


def test_llm_failure_never_breaks_the_query():
    class Boom:
        def generate(self, *a, **k):
            raise RuntimeError("down")
    p = QueryProcessor(Boom()).process("Quelle est la différence entre CM-IDLE et CM-CONNECTED ?")
    assert p.english.startswith("Quelle") and p.error == "down"


def test_helpers():
    assert is_smalltalk("hello!") and not is_smalltalk("hello what is the AMF")
    assert "Access and Mobility" in expand_acronyms("role of the AMF")


def test_pleasantries_never_reach_retrieval():
    from src.retrieval.query_processor import smalltalk_kind
    assert smalltalk_kind("Thank you.") == "thanks" and smalltalk_kind("Merci beaucoup") == "thanks"
    assert smalltalk_kind("Appreciated") == "thanks" and smalltalk_kind("hello!") == "greeting"
    assert smalltalk_kind("who are you?") == "identity"
    for real in ["hello what is the AMF", "ok explain registration", "help with registration",
                 "and T3511?", "thanks, now what is T3510"]:
        assert smalltalk_kind(real) is None


def test_rewriter_cannot_invent_a_spec_number():
    class Liar:
        def generate(self, *a, **k):
            return "What NAS messages are exchanged during registration as described in TS 23.502?"
    out = QueryProcessor._rewrite(Liar(), "and the NAS messages?", [{"role": "user", "content": "registration"}])
    assert "23.502" not in out

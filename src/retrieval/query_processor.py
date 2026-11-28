"""Query preprocessing: language detection, translation to English, follow-up condensation,
acronym expansion for BM25, and small-talk detection. LLM calls only when really needed."""
from __future__ import annotations

import re
from dataclasses import dataclass

_FR_STOP = {"le", "la", "les", "un", "une", "des", "du", "de", "est", "sont", "quel", "quelle", "quels",
            "quelles", "comment", "pourquoi", "quand", "que", "qui", "dans", "pour", "entre", "avec",
            "sur", "par", "et", "ou", "au", "aux", "ce", "cette", "ces", "signifie", "différence",
            "procédure", "fonctionne", "décris", "décrire", "explique", "expliquer", "quoi", "lors"}
_ACCENTS = re.compile(r"[àâäçéèêëîïôöùûüÿœæ]", re.I)
_ARABIC = re.compile(r"[\u0600-\u06FF]")
_FOLLOW_UP = re.compile(r"\b(it|its|that|this|those|these|them|they|their|also|too|same|other|previous|above|"
                        r"and what about|how about|what about|and for)\b", re.I)
ACRONYMS = {
    "amf": "Access and Mobility Management Function", "smf": "Session Management Function",
    "upf": "User Plane Function", "udm": "Unified Data Management", "ausf": "Authentication Server Function",
    "pcf": "Policy Control Function", "nrf": "Network Repository Function",
    "nssf": "Network Slice Selection Function", "nef": "Network Exposure Function",
    "nwdaf": "Network Data Analytics Function", "sepp": "Security Edge Protection Proxy",
    "seaf": "Security Anchor Function", "suci": "Subscription Concealed Identifier",
    "supi": "Subscription Permanent Identifier", "sidf": "Subscription Identifier De-concealing Function",
    "nas": "Non-Access Stratum", "pdu": "Protocol Data Unit", "ue": "User Equipment",
    "5gmm": "5GS mobility management", "5gsm": "5GS session management",
    "nssai": "Network Slice Selection Assistance Information",
    "s-nssai": "Single Network Slice Selection Assistance Information", "ssc": "Session and Service Continuity",
    "qfi": "QoS Flow Identifier", "5qi": "5G QoS Identifier", "dnn": "Data Network Name",
    "guti": "Globally Unique Temporary Identifier", "aka": "Authentication and Key Agreement",
    "rm": "Registration Management", "cm": "Connection Management", "sba": "Service Based Architecture",
}


def detect_language(text: str) -> str:
    if _ARABIC.search(text):
        return "ar"
    words = re.findall(r"[a-zàâäçéèêëîïôöùûüÿœæ']+", text.lower())
    if _ACCENTS.search(text) or sum(w in _FR_STOP for w in words) >= 2:
        return "fr"
    return "en"


_PLEASANTRIES = [   # checked in this order
    ("thanks", r"(thanks?|thank you|thank u|thx|ty|merci|shukran|cheers|appreciated?|many thanks|grateful|great job|good job|well done|nice work|bravo)"),
    ("bye", r"(bye|goodbye|see you|see ya|good night|au revoir|à bientôt|a bientot|bonne soirée|later)"),
    ("greeting", r"(hi|hello|hey|hola|yo|bonjour|salut|bonsoir|good (morning|afternoon|evening)|how are you|ça va|comment ça va)"),
    ("ack", r"(ok|okay|cool|nice|great|awesome|perfect|got it|i see|understood|makes sense|alright|sounds good|super|parfait|d'accord|compris|excellent|wow)"),
]
_IDENTITY = re.compile(r"^(who are you|what are you|what can you do|what do you do|help|help me|how do you work|qui es[- ]tu|que peux[- ]tu faire)$")
_REQUEST = re.compile(r"\b(what|how|why|when|which|where|who|explain|describe|tell|show|list|give|compare|summari[sz]e|detail|more|elaborate|continue|can you|could you|please|quel|quelle|quels|quelles|comment|pourquoi|quand|qui|que|dis|explique|décris)\b")
_TECH = re.compile(r"\d|\b(5g|3gpp|spec|specs|nas|ts|" + "|".join(re.escape(k) for k in ACRONYMS) + r")\b")

REPLIES = {
    "greeting": "Hi, I’m ChatGPP. Ask me anything about the 3GPP 5G specifications (TS 23.501, TS 24.501, TS 23.502, TS 33.501) and I’ll answer with citations.",
    "thanks": "You’re welcome! Ask me another question about the 5G specifications whenever you like.",
    "ack": "Glad that helps. What would you like to look up next?",
    "bye": "Goodbye! Come back any time you have a question about the 5G specifications.",
    "identity": "I’m ChatGPP. I answer questions about the 3GPP 5G specifications (TS 23.501, 24.501, 23.502 and 33.501) using only the documents, and I cite the section for every claim. I can also compare Release 17 and 18, and you can ask in English or French.",
}


def smalltalk_kind(text: str) -> str | None:
    """greeting | thanks | ack | bye | identity | None. Never fires on a real question."""
    t = " ".join(re.sub(r"[^\w\s'’àâçéèêëîïôûùü-]", " ", text.lower()).split())
    if not t:
        return None
    if _IDENTITY.match(t):
        return "identity"
    if len(t.split()) > 8 or "?" in text or _REQUEST.search(t) or _TECH.search(t):
        return None
    for kind, pat in _PLEASANTRIES:
        if re.search(rf"\b{pat}\b", t):
            return kind
    return None


def smalltalk_reply(text: str) -> str | None:
    kind = smalltalk_kind(text)
    return REPLIES[kind] if kind else None


def is_smalltalk(text: str) -> bool:
    return smalltalk_kind(text) is not None


def expand_acronyms(query: str) -> str:
    q = query.lower()
    extra = [full for ac, full in ACRONYMS.items() if re.search(rf"(?<![\w-]){re.escape(ac)}(?![\w-])", q)]
    return query if not extra else f"{query} {' '.join(extra[:6])}"


@dataclass
class ProcessedQuery:
    original: str
    english: str
    lexical: str
    language: str
    rewritten: bool = False
    error: str | None = None


REWRITE_SYSTEM = (
    "You rewrite user messages into search queries for a database of 3GPP 5G specifications "
    "(TS 23.501, TS 24.501, TS 23.502, TS 33.501).\n"
    "Rules:\n"
    "1. Output ONE English question and nothing else.\n"
    "2. Translate to English if the message is in another language.\n"
    "3. If chat history is given and the message depends on it (pronouns, ellipsis), make it fully standalone.\n"
    "4. Keep acronyms (AMF, SMF, 5GMM...), timers (T3510), cause numbers, message/IE names, release numbers "
    "and specification numbers EXACTLY as written.\n"
    "5. Do not answer the question and do not add facts.\n"
    "6. NEVER add a specification number (TS xx.xxx), release or topic that the user did not write. "
    "If the message is not a question or request about 5G (thanks, greeting, acknowledgement), output it unchanged."
)


class QueryProcessor:
    def __init__(self, llm=None):
        self.llm = llm
        self._cache: dict = {}

    def needs_rewrite(self, query: str, history: list[dict] | None) -> tuple[bool, str]:
        lang = detect_language(query)
        if lang != "en":
            return True, lang
        looks_like_request = "?" in query or bool(_REQUEST.search(query.lower()))
        if history and looks_like_request and (len(query.split()) <= 12 or _FOLLOW_UP.search(query)):
            return True, lang
        return False, lang

    def process(self, query: str, history: list[dict] | None = None, llm=None) -> ProcessedQuery:
        llm = llm or self.llm
        need, lang = self.needs_rewrite(query, history)
        english, rewritten, err = query, False, None
        if need and llm is not None:
            key = (query, tuple((h["role"], h["content"][:80]) for h in (history or [])[-4:]))
            if key in self._cache:
                english, rewritten = self._cache[key], True
            else:
                try:
                    english = self._rewrite(llm, query, history)
                    rewritten = english != query
                    self._cache[key] = english
                except Exception as e:  # translation must never break the chat
                    err = str(e)
        return ProcessedQuery(query, english, expand_acronyms(english), lang, rewritten, err)

    @staticmethod
    def _rewrite(llm, query: str, history: list[dict] | None) -> str:
        parts = []
        if history:
            parts.append("[Chat history]")
            for h in history[-4:]:
                parts.append(f"{h['role']}: {h['content'][:400]}")
        parts += ["[Message]", query]
        out = llm.generate(REWRITE_SYSTEM, "\n".join(parts), temperature=0.0)
        lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
        if not lines:
            return query
        text = re.sub(r"^(standalone question|question|english|translation)\s*:\s*", "", lines[0], flags=re.I)
        text = text.strip().strip('"“”\'')
        if not 3 <= len(text) <= 600:
            return query
        known = (query + " " + " ".join(h["content"] for h in (history or []))).replace(" ", "")
        for num in set(re.findall(r"\b\d{2}\.\d{3}\b", text)):
            if num not in known:   # the LLM invented a spec number: strip it, it would hard-filter retrieval
                text = re.sub(rf"(?:,?\s*(?:as\s+)?(?:described|specified|defined)?\s*in\s+)?TS\s*{re.escape(num)}", "", text)
        return " ".join(text.split()) or query

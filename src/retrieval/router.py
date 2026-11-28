"""Query router: which specification(s) and which release(s) does the question target?

Two kinds of output:
  * target_specs      -> HARD filter (explicit "TS 24.501" mention, or legacy 'high' confidence)
  * preferred_specs   -> SOFT prior (boost + coverage guarantee), never loses recall
  * releases/compare  -> "Rel-17", "Release 18", "compare Rel-17 and Rel-18"
"""
import re
from dataclasses import dataclass, field

SPECS = ["TS 23.501", "TS 24.501", "TS 23.502", "TS 33.501"]


@dataclass
class RouteDecision:
    target_specs: list[str] | None
    confidence: str                       # explicit | high | cross_spec
    reason: str
    preferred_specs: list[str] = field(default_factory=list)
    releases: list[str] | None = None
    compare: bool = False


class QueryRouter:
    PATTERNS = {
        "TS 23.501": [
            r"\b(amf|smf|upf|udm|ausf|pcf|nrf|nssf|nef|nwdaf|scp|sepp|udr|ucmf)\b",
            r"\b(n[1-9]|n1[0-5]|namf|nsmf|nudm|npcf|nnrf|nnssf)\b",
            r"\b(5qi|gbr|non-gbr|qos flow|reflective qos|ssc modes?)\b",
            r"\b(service[- ]based architecture|sba|network slicing|edge computing|urllc)\b",
            r"\b(reference point|functional entity|stage 2|architecture)\b",
            r"\b(rm-(?:de)?registered|cm-idle|cm-connected|s-nssai|nssai)\b",
        ],
        "TS 24.501": [
            r"\bt3[45]\d{2}\b",
            r"\b(5gmm|5gsm)[-\s]?(registered|deregistered|idle|connected|cause|status|state|states)\b",
            r"\bcause\s*#?\d+\b",
            r"\b(information element|iei|octet|message type|nas message|nas messages|stage 3)\b",
            r"\b(registration accept|registration reject|pdu session establishment accept)\b",
            r"\b(security mode command|authentication reject|identity request|de-?registration)\b",
            r"\b(5g-s-tmsi|5g-guti|ue radio capability|abnormal cases in the ue)\b",
        ],
        "TS 23.502": [
            r"\b(call flow|signalling flow|message flow|stage 2 procedures?)\b",
            r"\b(registration|service request|pdu session (?:establishment|modification|release)|handover|paging|de-?registration) procedures?\b",
            r"\b(xn|n2|inter[- ]?ng-?ran|inter[- ]?system) handover\b",
            r"\b(eps fallback|n26 interface|interworking with (?:eps|epc))\b",
            r"\b(ue|network)[- ](?:triggered|initiated|requested) (?:service request|pdu session|de-?registration)\b",
            r"\b(nnrf|nsmf|namf|nudm|npcf)_\w+",
        ],
        "TS 33.501": [
            r"\b(5g[- ]aka|eap[- ]aka'?|suci|supi|sidf|seaf|arpf)\b",
            r"\b(kamf|kausf|kseaf|kgnb|knasint|knasenc|key hierarchy|key derivation)\b",
            r"\b(nea[0-3]|nia[0-3]|security context|security anchor|authentication vector)\b",
            r"\b(subscription (?:permanent|concealed) identifier|home network public key)\b",
            r"\b(integrity protection|ciphering|confidentiality|security (?:algorithm|requirement|procedure)s?)\b",
            r"\b(primary authentication|secondary authentication|nas security|up security|n32|nds)\b",
        ],
    }
    REL_RE = re.compile(r"\brel(?:ease)?[-\s_]*(\d{2})\b")
    CMP_RE = re.compile(r"\b(compare|comparison|differences?|differ|differs|changed?|changes|evolv\w+|what'?s new|what is new|versus|vs)\b")

    def route(self, query: str) -> RouteDecision:
        q = query.lower()
        explicit = [s for s in SPECS if re.search(rf"\b{re.escape(s[3:])}\b", q)]

        scores = {s: sum(1 for p in pats if re.search(p, q)) for s, pats in self.PATTERNS.items()}
        positive = [s for s, v in sorted(scores.items(), key=lambda kv: -kv[1]) if v > 0]

        mentioned = sorted(set(self.REL_RE.findall(q)))
        cmp_kw = bool(self.CMP_RE.search(q))
        compare = len(mentioned) >= 2 or (cmp_kw and (bool(mentioned) or bool(re.search(r"\breleases\b", q))))
        releases = mentioned or None

        common = dict(releases=releases, compare=compare)
        if explicit:
            pref = explicit + [s for s in positive if s not in explicit]
            return RouteDecision(explicit, "explicit", f"Explicit mention of {', '.join(explicit)}",
                                 preferred_specs=pref, **common)
        if len(positive) == 1:
            return RouteDecision(positive, "high", f"Single-spec cues (score={scores[positive[0]]})",
                                 preferred_specs=positive, **common)
        return RouteDecision(None, "cross_spec", "Cross-spec or general query " +
                             "(" + ", ".join(f"{s[3:]}={v}" for s, v in scores.items()) + ")",
                             preferred_specs=positive, **common)

import re
from dataclasses import dataclass


@dataclass
class RouteDecision:
    target_specs: list[str] | None
    confidence: str
    reason: str


class QueryRouter:
    """Routes 3GPP 5G queries to TS 23.501, TS 24.501, or both when cross-layer."""

    TS_23501_PATTERNS = [
        r"\b(amf|smf|upf|udm|ausf|pcf|nrf|nssf|nef|nwdaf|scp|sepp|udr|ucmf)\b",
        r"\b(n[1-9]|n1[0-5]|namf|nsmf|nudm|npcf|nnrf|nnssf)\b",
        r"\b(5qi|gbr|non-gbr|qos flow|reflective qos|ssc mode)\b",
        r"\b(service[- ]based architecture|sba|network slicing|edge computing|urllc)\b",
        r"\b(reference point|functional entity|stage 2|architecture)\b",
    ]

    TS_24501_PATTERNS = [
        r"\bt3[45]\d{2}\b",
        r"\b(5gmm|5gsm)[-\s]?(registered|deregistered|idle|connected|cause|status|state|states)\b",
        r"\bcause\s*#?\d+\b",
        r"\b(information element|iei|octet|message type|nas message|nas messages|stage 3)\b",
        r"\b(registration accept|registration reject|pdu session establishment accept)\b",
        r"\b(security mode command|authentication reject|identity request|deregistration)\b",
        r"\b(5g-s-tmsi|5g-guti|ue radio capability|abnormal cases in the ue)\b",
    ]

    def route(self, query: str) -> RouteDecision:
        q = query.lower()

        has_23501 = bool(re.search(r"\b23\.501\b", q))
        has_24501 = bool(re.search(r"\b24\.501\b", q))

        if has_23501 and not has_24501:
            return RouteDecision(["TS 23.501"], "explicit", "Explicit mention of TS 23.501")
        if has_24501 and not has_23501:
            return RouteDecision(["TS 24.501"], "explicit", "Explicit mention of TS 24.501")
        if has_23501 and has_24501:
            return RouteDecision(None, "cross_spec", "Both specifications explicitly mentioned")

        score_23 = sum(1 for p in self.TS_23501_PATTERNS if re.search(p, q))
        score_24 = sum(1 for p in self.TS_24501_PATTERNS if re.search(p, q))

        if score_23 >= 1 and score_24 == 0:
            return RouteDecision(["TS 23.501"], "high", f"Architecture/SBA cues (score={score_23})")
        if score_24 >= 1 and score_23 == 0:
            return RouteDecision(["TS 24.501"], "high", f"NAS protocol/timer cues (score={score_24})")

        return RouteDecision(
            None,
            "cross_spec",
            f"Cross-spec or general query (23.501={score_23}, 24.501={score_24})",
        )
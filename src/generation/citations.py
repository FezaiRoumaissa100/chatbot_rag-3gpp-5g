"""Citation parsing and verification against the retrieved chunks."""
import re

CITE_RE = re.compile(
    r"\[\s*TS\s*(\d{2}\.\d{3})(?:\s*\(?\s*Rel(?:ease)?[-\s]*(\d{2})\)?)?\s*,\s*(?:Section|Sec\.?|Clause)\s*"
    r"(Annex\s+[A-Z](?:\.\w+)*|\d+(?:\.\w+)*|[A-Z](?:\.\w+)+)\s*\]", re.IGNORECASE)


def extract_citations(answer: str) -> list[dict]:
    return [{"raw": m.group(0), "specification": f"TS {m.group(1)}", "release": m.group(2),
             "section": re.sub(r"\s+", " ", m.group(3)).strip()} for m in CITE_RE.finditer(answer or "")]


def section_matches(chunk_section: str, cited: str) -> bool:
    a, b = str(chunk_section).strip(), cited.strip()
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def validate_citations(answer: str, chunks: list[dict]) -> dict:
    """A citation is valid when a retrieved chunk has the same spec (and release, if cited) and section."""
    items = []
    for c in extract_citations(answer):
        ok = any(
            ch["metadata"]["specification"] == c["specification"]
            and (not c["release"] or str(ch["metadata"].get("release")) == c["release"])
            and section_matches(ch["metadata"]["section"], c["section"])
            for ch in chunks)
        items.append({**c, "valid": ok})
    valid = sum(i["valid"] for i in items)
    return {"total": len(items), "valid": valid,
            "accuracy": (valid / len(items)) if items else None, "items": items}

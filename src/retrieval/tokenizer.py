"""Shared BM25 tokenizer (used at index time AND query time - never duplicate it)."""
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")


def _stem(tok: str) -> str:
    """Cheap plural normalisation; identifiers (t3510, 5gmm-idle, 23.501) are untouched."""
    if len(tok) > 4 and tok.isalpha():
        if tok.endswith("ies"):
            return tok[:-3] + "y"
        if tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
            return tok[:-1]
    return tok


def tokenize_3gpp(text: str) -> list[str]:
    """Keeps hyphenated identifiers AND their parts: '5gmm-registered' -> ['5gmm-registered','5gmm','registered']."""
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        out.append(_stem(tok))
        if "-" in tok:
            out.extend(_stem(p) for p in tok.split("-") if len(p) > 1)
    return out

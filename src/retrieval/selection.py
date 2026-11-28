"""Spec-coverage selection: for cross-spec questions, make sure each relevant spec is represented."""


def balance_specs(ranked: list[dict], preferred: list[str], k: int, min_per: int) -> list[dict]:
    spec = lambda c: c["metadata"]["specification"]
    chosen = list(ranked[:k])
    present = {spec(c) for c in ranked}
    preferred = [p for p in preferred if p in present]
    if len(preferred) < 2:
        return chosen

    order = {id(c): i for i, c in enumerate(ranked)}
    count = lambda sp: sum(1 for c in chosen if spec(c) == sp)

    def victim():
        for c in sorted(chosen, key=lambda c: order[id(c)], reverse=True):
            s = spec(c)
            if s not in preferred or count(s) > min_per:
                return c
        return None

    for sp in preferred:
        while count(sp) < min_per:
            ids = {id(c) for c in chosen}
            add = next((c for c in ranked if spec(c) == sp and id(c) not in ids), None)
            v = victim()
            if add is None or v is None:
                break
            chosen = [c for c in chosen if c is not v] + [add]
    chosen.sort(key=lambda c: order[id(c)])
    return chosen

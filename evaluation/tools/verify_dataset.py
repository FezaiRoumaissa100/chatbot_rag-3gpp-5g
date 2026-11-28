"""Checks that every expected section of a dataset exists in chunks.json (catches wrong section numbers).

    python evaluation/tools/verify_dataset.py evaluation/eval_dataset_ext.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "data" / "processed" / "chunks.json"


def main(path):
    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    titles = {}
    for c in chunks:
        titles[(c["specification"], str(c["release"]), c["section"])] = c["title"]
    bad = 0
    for it in json.loads(Path(path).read_text(encoding="utf-8")):
        for e in it.get("expected_sections", []):
            rels = [e["release"]] if e.get("release") else sorted({r for (_, r, _) in titles})
            for rel in rels:
                hits = [(s, t) for (sp, r, s), t in titles.items()
                        if sp == e["specification"] and r == rel and (s == e["section"] or s.startswith(e["section"] + "."))]
                if hits:
                    print(f"OK   {it['id']} {e['specification']} Rel-{rel} §{e['section']}  {hits[0][1][:60]}  (+{len(hits)-1} sub)")
                else:
                    bad += 1
                    prefix = ".".join(e["section"].split(".")[:2])
                    sib = sorted({f"{s} {t[:40]}" for (sp, r, s), t in titles.items()
                                  if sp == e["specification"] and r == rel and s.startswith(prefix)})[:6]
                    print(f"MISS {it['id']} {e['specification']} Rel-{rel} §{e['section']}  -> nearby: {sib}")
    print(f"\n{bad} missing section(s)")


if __name__ == "__main__":
    main(sys.argv[1])

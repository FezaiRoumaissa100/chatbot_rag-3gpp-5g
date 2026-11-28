"""Shows exactly what is in your corpus and indexes (run this when retrieval looks empty).

    python evaluation/tools/inspect_index.py
"""
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.config import cfg  # noqa: E402

print("config corpus section :", repr(cfg("corpus")))

raw = ROOT / cfg("corpus")["raw_dir"]
print(f"\n[1] files in {raw}:")
for p in sorted(raw.glob("*")):
    print("   ", p.name)
try:
    from src.corpus import discover_specs
    found = discover_specs(raw)
    print("[1b] discovered by the loader:")
    for f in found:
        print(f"    {f.specification} Rel-{f.release} {f.version}  <- {f.path.name}")
    if not found:
        print("    NOTHING (file names must look like TS_23.501_V18.12.0.docx)")
except Exception as e:
    print("    discover failed:", e)

mf = ROOT / "data/processed/corpus_manifest.json"
print("\n[2] manifest written by the last parser run:", mf.read_text() if mf.exists() else "MISSING (parser not run with the new code)")

ch = ROOT / "data/processed/chunks.json"
if ch.exists():
    chunks = json.loads(ch.read_text(encoding="utf-8"))
    print(f"\n[3] chunks.json: {len(chunks)} chunks")
    for (s, r), n in sorted(Counter((c["specification"], repr(c["release"])) for c in chunks).items()):
        print(f"    {s}  release={r}  {n}")
    print("    has 'version' field:", "version" in chunks[0], "| chunk_id example:", chunks[0]["chunk_id"])
else:
    print("\n[3] chunks.json MISSING")

bm = ROOT / "data/index/bm25_index.pkl"
if bm.exists():
    print(f"\n[4] BM25 index: {len(pickle.load(open(bm, 'rb'))['chunk_ids'])} chunks")

try:
    import chromadb
    client = chromadb.PersistentClient(path=str(ROOT / "data/index/chroma_db"))
    print("\n[5] Chroma collections:")
    for c in client.list_collections():
        col = client.get_collection(getattr(c, "name", c))
        metas = col.get(include=["metadatas"])["metadatas"]
        print(f"    {col.name}: {col.count()} vectors")
        for (s, r), n in sorted(Counter((m.get("specification"), repr(m.get("release"))) for m in metas).items()):
            print(f"        {s} release={r}: {n}")
except Exception as e:
    print("\n[5] Chroma not readable:", e)

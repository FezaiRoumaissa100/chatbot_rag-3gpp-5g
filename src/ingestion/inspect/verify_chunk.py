import json
from pathlib import Path

# Remonte de 3 niveaux depuis src/ingestion/inspect/verify_chunk.py vers rag-3gpp-5g
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.json"

with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

# 1. Contrôles automatiques de validité
oversized = [c for c in chunks if c["char_count"] > 1600]
empty_meta = [c for c in chunks if not c["specification"] or not c["section"]]

print(f"Total chunks          : {len(chunks)}")
print(f"Chunks > 1600 chars   : {len(oversized)} (doit être 0)")
print(f"Métadonnées manquantes: {len(empty_meta)} (doit être 0)")

# 2. Afficher deux chunks consécutifs d'un grand tableau découpé
print("\n" + "=" * 70)
print("EXEMPLE 1 : GRAND TABLEAU DÉCOUPÉ (EN-TÊTE RÉPÉTÉ)")
print("=" * 70)
for i in range(len(chunks) - 1):
    if (
        chunks[i]["has_table"]
        and chunks[i + 1]["has_table"]
        and chunks[i]["section"] == chunks[i + 1]["section"]
        and chunks[i]["specification"] == "TS 24.501"
    ):
        print(f"--- {chunks[i]['chunk_id']} ({chunks[i]['char_count']} chars) ---")
        print(chunks[i]["text"][:550] + "\n[...]")
        print(f"\n--- {chunks[i+1]['chunk_id']} ({chunks[i+1]['char_count']} chars) ---")
        print(chunks[i + 1]["text"][:550] + "\n[...]")
        break

# 3. Afficher deux chunks consécutifs d'une longue section (avec overlap)
print("\n" + "=" * 70)
print("EXEMPLE 2 : LONGUE SECTION DÉCOUPÉE (CHEVAUCHEMENT / OVERLAP)")
print("=" * 70)
for i in range(len(chunks) - 1):
    if (
        not chunks[i]["has_table"]
        and not chunks[i + 1]["has_table"]
        and chunks[i]["section"] == chunks[i + 1]["section"]
        and chunks[i]["specification"] == "TS 23.501"
        and chunks[i]["section"] not in ("2", "3.1", "3.2")
    ):
        print(f"--- FIN DE {chunks[i]['chunk_id']} ---")
        print("[...]\n" + chunks[i]["text"][-400:])
        print(f"\n--- DÉBUT DE {chunks[i+1]['chunk_id']} ---")
        print(chunks[i + 1]["text"][:450] + "\n[...]")
        break
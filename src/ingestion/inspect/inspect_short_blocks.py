
from pathlib import Path
import json
from docx import Document


# ============================================================
# 1. CONFIGURATION DES CHEMINS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

JSON_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "parsed_blocks.json"
)

DOCUMENTS = {
    "TS 23.501": (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "TS_23.501_V18.12.0.docx"
    ),
    "TS 24.501": (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "TS_24.501_V18.14.0.docx"
    )
}

MAX_SHORT_BLOCKS = 15
MAX_CONTEXT_LENGTH = 400
MAX_WORDS = 3


# ============================================================
# 2. CHARGEMENT DU JSON
# ============================================================

if not JSON_FILE.exists():
    raise FileNotFoundError(
        f"Fichier JSON introuvable : {JSON_FILE}"
    )

with open(JSON_FILE, "r", encoding="utf-8") as f:
    blocks = json.load(f)

print(f"Fichier JSON chargé : {JSON_FILE}")


# ============================================================
# 3. FONCTION D'AFFICHAGE
# ============================================================

def display_context(label, block):

    if block is None:
        print(f"\n[{label}] Aucun bloc")
        return

    print(f"\n[{label}]")
    print(f"Type : {block.get('type', 'Inconnu')}")
    print(f"Style : {block.get('style', 'Non renseigné')}")
    print(f"Section : {block.get('section', 'Non renseignée')}")

    text = block.get("text", "")

    print(f"Texte : {text[:MAX_CONTEXT_LENGTH]}")


# ============================================================
# 4. ANALYSE DE CHAQUE DOCUMENT
# ============================================================

for spec, doc_path in DOCUMENTS.items():

    print("\n" + "=" * 80)
    print(f"DOCUMENT : {spec}")
    print("=" * 80)

    if not doc_path.exists():
        print(f"Document introuvable : {doc_path}")
        continue

    # Récupérer les blocs de la spécification
    spec_blocks = [
        block for block in blocks
        if block.get("specification") == spec
    ]

    # --------------------------------------------------------
    # A. COMPARAISON DU NOMBRE DE TABLEAUX
    # --------------------------------------------------------

    original_doc = Document(doc_path)

    original_table_count = len(original_doc.tables)

    extracted_tables = [
        block for block in spec_blocks
        if block.get("type") == "table"
    ]

    print("\n" + "-" * 80)
    print("A. VERIFICATION DES TABLEAUX")
    print("-" * 80)

    print(f"Tableaux dans le DOCX : {original_table_count}")
    print(f"Tableaux dans le JSON : {len(extracted_tables)}")

    difference = original_table_count - len(extracted_tables)

    print(f"Différence : {difference}")

    if difference == 0:
        print("Résultat : Tous les tableaux semblent extraits.")
    else:
        print("Résultat : Différence à examiner.")

    # --------------------------------------------------------
    # B. RECHERCHE DES PARAGRAPHES COURTS
    # --------------------------------------------------------

    print("\n" + "-" * 80)
    print("B. PARAGRAPHES COURTS ET LEUR CONTEXTE")
    print("-" * 80)

    displayed = 0
    short_blocks_count = 0

    for i, block in enumerate(spec_blocks):

        # On ignore les tableaux
        if block.get("type") != "paragraph":
            continue

        text = block.get("text", "").strip()

        word_count = len(text.split())

        # Détecter les paragraphes de 1 à 3 mots
        if 0 < word_count <= MAX_WORDS:

            short_blocks_count += 1

            # Limiter le nombre d'exemples affichés
            if displayed >= MAX_SHORT_BLOCKS:
                continue

            print("\n" + "=" * 70)
            print(f"EXEMPLE {displayed + 1}")
            print("=" * 70)

            print(f"Position dans le JSON : {i}")
            print(f"Nombre de mots : {word_count}")
            print(f"Section : {block.get('section')}")
            print(f"Titre : {block.get('title')}")
            print(f"Hiérarchie : {block.get('hierarchy')}")
            print(f"Style : {block.get('style')}")

            # Bloc précédent
            previous = (
                spec_blocks[i - 1]
                if i > 0
                else None
            )

            display_context("PRECEDENT", previous)

            # Bloc actuel
            display_context("PARAGRAPHE COURT", block)

            # Bloc suivant
            following = (
                spec_blocks[i + 1]
                if i + 1 < len(spec_blocks)
                else None
            )

            display_context("SUIVANT", following)

            displayed += 1

    # --------------------------------------------------------
    # C. BILAN
    # --------------------------------------------------------

    print("\n" + "-" * 80)
    print("C. BILAN DES PARAGRAPHES COURTS")
    print("-" * 80)

    print(
        f"Nombre total de paragraphes de "
        f"{MAX_WORDS} mots ou moins : {short_blocks_count}"
    )

    print(
        f"Nombre d'exemples affichés : {displayed}"
    )

    if short_blocks_count > MAX_SHORT_BLOCKS:
        print(
            f"{short_blocks_count - MAX_SHORT_BLOCKS} "
            "autres paragraphes courts non affichés."
        )


print("\n" + "=" * 80)
print("ANALYSE TERMINEE")
print("=" * 80)

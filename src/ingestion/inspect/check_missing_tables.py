
from pathlib import Path
from collections import Counter
import json
import re

from docx import Document
from docx.table import Table
from docx.oxml.table import CT_Tbl


# ============================================================
# 1. CONFIGURATION
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
        PROJECT_ROOT / "data" / "raw"
        / "TS_23.501_V18.12.0.docx"
    ),
    "TS 24.501": (
        PROJECT_ROOT / "data" / "raw"
        / "TS_24.501_V18.14.0.docx"
    )
}


# ============================================================
# 2. NORMALISATION DU TEXTE
# ============================================================

def normalize(text):
    """Uniformiser les espaces pour comparer les tableaux."""

    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# 3. EXTRACTION DU TEXTE D'UN TABLEAU
# ============================================================

def extract_table_text(table):

    rows_text = []

    for row in table.rows:

        cells_text = [
            cell.text.strip()
            for cell in row.cells
        ]

        rows_text.append(" | ".join(cells_text))

    return "\n".join(rows_text)


# ============================================================
# 4. CHARGEMENT DU JSON
# ============================================================

with open(JSON_FILE, "r", encoding="utf-8") as f:
    blocks = json.load(f)


# ============================================================
# 5. COMPARAISON DES TABLEAUX
# ============================================================

for spec, doc_path in DOCUMENTS.items():

    print("\n" + "=" * 80)
    print(f"DOCUMENT : {spec}")
    print("=" * 80)

    doc = Document(doc_path)

    # Tous les tableaux directement présents dans le corps
    original_tables = []

    for element in doc.element.body.iterchildren():

        if isinstance(element, CT_Tbl):

            table = Table(element, doc)

            original_tables.append(
                extract_table_text(table)
            )

    # Tableaux extraits dans le JSON
    json_tables = [
        block.get("text", "")
        for block in blocks
        if (
            block.get("specification") == spec
            and block.get("type") == "table"
        )
    ]

    print(f"\nTableaux dans le DOCX : {len(original_tables)}")
    print(f"Tableaux dans le JSON : {len(json_tables)}")

    # Comparaison des contenus normalisés
    json_counter = Counter(
        normalize(text)
        for text in json_tables
    )

    missing_tables = []

    for index, table_text in enumerate(original_tables):

        normalized = normalize(table_text)

        if json_counter[normalized] > 0:
            json_counter[normalized] -= 1

        else:
            missing_tables.append(
                (index + 1, table_text)
            )

    # Affichage des résultats
    print("\n" + "-" * 80)
    print("TABLEAUX NON RETROUVES DANS LE JSON")
    print("-" * 80)

    if not missing_tables:

        print(
            "Aucun tableau manquant détecté "
            "par comparaison exacte du texte normalisé."
        )

    else:

        for index, table_text in missing_tables:

            print(f"\nTABLEAU ORIGINAL N° {index}")
            print("-" * 50)

            if table_text.strip():
                print(table_text[:1500])
            else:
                print("[TABLEAU VIDE]")

    print("\n" + "=" * 80)
    print("FIN DE L'ANALYSE")
    print("=" * 80)

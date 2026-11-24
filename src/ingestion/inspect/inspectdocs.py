"""Inspection des deux specs .docx : styles, titres, tableaux.

Usage (depuis la racine du repo) :
    pip install python-docx
    python inspect_docx.py
"""

from collections import Counter
from pathlib import Path

from docx import Document

FILES = [
    "data/raw/TS_23.501_V18.12.0.docx",
    "data/raw/TS_24.501_V18.14.0.docx",
]
OUT = Path("data/processed/inspection.txt")
lines = []


def log(text=""):
    print(text)
    lines.append(text)


for f in FILES:
    log("=" * 70)
    log(f"FICHIER : {f}")
    if not Path(f).exists():
        log("  -> introuvable, vérifie le chemin")
        continue

    doc = Document(f)
    paragraphs = doc.paragraphs
    log(f"Paragraphes : {len(paragraphs)}")
    log(f"Tableaux    : {len(doc.tables)}")

    # Styles utilisés (top 15)
    styles = Counter(p.style.name for p in paragraphs if p.text.strip())
    log("\nStyles les plus fréquents (style : nombre de paragraphes) :")
    for name, n in styles.most_common(15):
        log(f"  {name:30s} {n}")

    # Paragraphes dont le style ressemble à un titre
    headings = [p for p in paragraphs
                if p.text.strip() and p.style.name.lower().startswith("heading")]
    log(f"\nParagraphes avec style 'Heading...' : {len(headings)}")
    log("Les 40 premiers (style | texte) :")
    for p in headings[:40]:
        log(f"  [{p.style.name}] {p.text.strip()[:90]}")

    # Lignes de table des matières (à exclure plus tard)
    toc = [p for p in paragraphs if p.style.name.lower().startswith("toc")]
    log(f"\nParagraphes de table des matières (style 'TOC...') : {len(toc)}")

    # Aperçu d'un tableau
    if doc.tables:
        t = doc.tables[min(50, len(doc.tables) - 1)]
        log(f"\nExemple de tableau (lignes={len(t.rows)}, colonnes={len(t.columns)}) :")
        for row in t.rows[:3]:
            log("  | " + " | ".join(c.text.strip()[:25] for c in row.cells))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
log(f"\nRapport enregistré dans {OUT}")
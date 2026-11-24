
from collections import Counter, defaultdict
from pathlib import Path

from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table


FILES = [
    "data/raw/TS_23.501_V18.12.0.docx",
    "data/raw/TS_24.501_V18.14.0.docx",
]

OUT = Path("data/processed/structure_details.txt")
lines = []


def log(text=""):
    print(text)
    lines.append(text)


for file_path in FILES:
    log("\n" + "=" * 80)
    log(f"FICHIER : {file_path}")
    log("=" * 80)

    if not Path(file_path).exists():
        log("Fichier introuvable.")
        continue

    doc = Document(file_path)

    # 1. Examiner les styles personnalisés
    samples = defaultdict(list)
    counts = Counter()

    for p in doc.paragraphs:
        if not p.text.strip():
            continue

        style = p.style.name
        counts[style] += 1

        if style not in samples and len(samples[style]) == 0:
            samples[style].append(p.text.strip()[:180])
        elif len(samples[style]) < 3:
            samples[style].append(p.text.strip()[:180])

    log("\n--- EXEMPLES DE STYLES PERSONNALISES ---")

    custom_styles = [
        "B1", "B2", "B3", "B4",
        "NO", "EW", "EX", "TF", "TH"
    ]

    for style in custom_styles:
        log(f"\nStyle : {style} | Nombre : {counts[style]}")

        for sample in samples[style]:
            log(f"  - {sample}")

    # 2. Examiner l'ordre réel paragraphes / tableaux
    log("\n--- PREMIERS BLOCS DANS LEUR ORDRE REEL ---")

    body = doc.element.body

    for index, element in enumerate(body.iterchildren()):
        if index >= 100:
            break

        if isinstance(element, CT_P):
            p = Paragraph(element, doc)

            if p.text.strip():
                log(
                    f"[{index}] PARAGRAPHE "
                    f"| {p.style.name} "
                    f"| {p.text.strip()[:130]}"
                )

        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)

            first_row = table.rows[0] if table.rows else None

            if first_row:
                preview = " | ".join(
                    cell.text.strip().replace("\n", " ")[:35]
                    for cell in first_row.cells
                )
                log(
                    f"[{index}] TABLEAU "
                    f"| lignes={len(table.rows)} "
                    f"| colonnes={len(table.columns)} "
                    f"| {preview}"
                )

    # 3. Examiner les positions des styles TOC et Heading
    log("\n--- POSITION DE LA TABLE DES MATIERES ---")

    toc_positions = []
    heading_positions = []

    for index, element in enumerate(body.iterchildren()):
        if not isinstance(element, CT_P):
            continue

        p = Paragraph(element, doc)
        style = p.style.name.lower()

        if style.startswith("toc"):
            toc_positions.append((index, p.text.strip()[:100]))

        if style.startswith("heading"):
            heading_positions.append((index, p.text.strip()[:100]))

    log(f"Nombre de blocs TOC : {len(toc_positions)}")
    log(f"Nombre de blocs Heading : {len(heading_positions)}")

    if toc_positions:
        log(f"Premier TOC : {toc_positions[0]}")
        log(f"Dernier TOC : {toc_positions[-1]}")

    if heading_positions:
        log(f"Premier Heading : {heading_positions[0]}")
        log(f"Dernier Heading : {heading_positions[-1]}")


OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")

print(f"\nRapport enregistré dans : {OUT}")

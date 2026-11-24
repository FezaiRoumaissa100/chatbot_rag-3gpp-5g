
from pathlib import Path
import json
from statistics import mean, median
from collections import Counter

# 1. Déterminer le chemin du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 2. Charger le résultat du parsing
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "parsed_blocks.json"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    blocks = json.load(f)


# 3. Analyser chaque spécification
specifications = ["TS 23.501", "TS 24.501"]

for spec in specifications:

    spec_blocks = [
        block for block in blocks
        if block.get("specification") == spec
    ]

    paragraphs = [
        block for block in spec_blocks
        if block.get("type") == "paragraph"
    ]

    tables = [
        block for block in spec_blocks
        if block.get("type") == "table"
    ]

    # Nombre de mots par paragraphe
    lengths = [
        len(block.get("text", "").split())
        for block in paragraphs
    ]

    print("\n" + "=" * 60)
    print(f"ANALYSE : {spec}")
    print("=" * 60)

    print(f"Nombre total de blocs : {len(spec_blocks)}")
    print(f"Nombre de paragraphes : {len(paragraphs)}")
    print(f"Nombre de tableaux : {len(tables)}")

    if lengths:
        print(f"\nNombre minimum de mots : {min(lengths)}")
        print(f"Nombre maximum de mots : {max(lengths)}")
        print(f"Moyenne : {mean(lengths):.2f}")
        print(f"Médiane : {median(lengths):.2f}")

    # Répartition des paragraphes par longueur
    categories = {
        "1-20 mots": 0,
        "21-50 mots": 0,
        "51-100 mots": 0,
        "101-200 mots": 0,
        "Plus de 200 mots": 0
    }

    for length in lengths:
        if length <= 20:
            categories["1-20 mots"] += 1
        elif length <= 50:
            categories["21-50 mots"] += 1
        elif length <= 100:
            categories["51-100 mots"] += 1
        elif length <= 200:
            categories["101-200 mots"] += 1
        else:
            categories["Plus de 200 mots"] += 1

    print("\nRépartition des paragraphes :")

    for category, count in categories.items():
        percentage = count / len(paragraphs) * 100 if paragraphs else 0
        print(f"{category}: {count} ({percentage:.1f}%)")

    # Sections les plus présentes
    section_counts = Counter(
        block.get("section", "Sans section")
        for block in paragraphs
    )

    print("\nLes 10 sections contenant le plus de paragraphes :")

    for section, count in section_counts.most_common(10):
        print(f"Section {section}: {count} paragraphes")

    # Exemples de paragraphes courts
    shortest = sorted(
        paragraphs,
        key=lambda block: len(block.get("text", "").split())
    )[:5]

    print("\n5 exemples de paragraphes les plus courts :")

    for block in shortest:
        print(f"- [{len(block.get('text', '').split())} mots] "
              f"{block.get('text', '')[:200]}")

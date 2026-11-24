import json
import re
from pathlib import Path
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl

# ============================================================
# 1. PATH CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. PARSING FUNCTION
# ============================================================

def parse_3gpp_document(file_path: Path, specification: str, release: str) -> list[dict]:
    """
    Parses a 3GPP Word (.docx) specification sequentially, ignoring cover pages,
    Table of Contents, and Change History annexes, while extracting section metadata.
    """
    print(f"\nParsing {specification}...")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    doc = Document(file_path)
    body = doc.element.body

    blocks = []
    capture_started = False
    heading_stack = {}
    current_section = ""
    current_title = ""

    # Matches numbered sections like "4.2.1", "4.2.5a", "4.8.4A" followed by title
    section_pattern = re.compile(r'^(\d+(?:\.\d+)*[a-zA-Z]?)\s+(.*)')

    for element in body.iterchildren():

        # ----------------------------------------------------
        # CASE 1: PARAGRAPH
        # ----------------------------------------------------
        if isinstance(element, CT_P):
            paragraph = Paragraph(element, doc)
            text = paragraph.text.strip()

            if not text:
                continue

            style_name = paragraph.style.name if paragraph.style else ""

            # Start capturing at the first real Heading 1 ("Foreword")
            if style_name == "Heading 1" and "Foreword" in text:
                capture_started = True

            if not capture_started:
                continue

            # Stop capturing when reaching the administrative Change History annex
            if style_name == "Heading 1" and "Change history" in text:
                break

            # Detect Heading 1 to Heading 5
            if style_name.startswith("Heading"):
                try:
                    level = int(style_name.replace("Heading", "").strip())
                except ValueError:
                    level = None

                if level is not None:
                    # Clean newlines inside headings (e.g., "Annex A (normative):\nTitle")
                    clean_heading = text.replace("\n", " ")
                    heading_stack[level] = clean_heading

                    for key in list(heading_stack.keys()):
                        if key > level:
                            del heading_stack[key]

                    match = section_pattern.match(clean_heading)
                    if match:
                        current_section = match.group(1)
                        current_title = match.group(2).strip()
                    else:
                        # Handle Annexes (e.g., "Annex A (normative): ...")
                        current_section = clean_heading.split(":")[0].strip()
                        current_title = clean_heading

                continue

            # Skip standalone Figure captions (since images are not extracted)
            if style_name == "TF":
                continue

            section_path = " > ".join(
                heading_stack[level] for level in sorted(heading_stack)
            )

            blocks.append({
                "type": "paragraph",
                "text": text,
                "style": style_name,
                "specification": specification,
                "release": release,
                "section": current_section,
                "title": current_title,
                "hierarchy": section_path,
            })

        # ----------------------------------------------------
        # CASE 2: TABLE
        # ----------------------------------------------------
        elif isinstance(element, CT_Tbl) and capture_started:
            table = Table(element, doc)
            rows = []

            for row in table.rows:
                cells = [
                    cell.text.strip().replace("\n", " ")
                    for cell in row.cells
                ]
                rows.append(" | ".join(cells))

            table_text = "\n".join(rows)

            if not table_text.strip():
                continue

            section_path = " > ".join(
                heading_stack[level] for level in sorted(heading_stack)
            )

            blocks.append({
                "type": "table",
                "text": table_text,
                "specification": specification,
                "release": release,
                "section": current_section,
                "title": current_title,
                "hierarchy": section_path,
            })

    print(f"Extracted blocks count: {len(blocks)}")
    return blocks


# ============================================================
# 3. MAIN EXECUTION
# ============================================================

def main():
    doc_23501 = RAW_DIR / "TS_23.501_V18.12.0.docx"
    doc_24501 = RAW_DIR / "TS_24.501_V18.14.0.docx"

    print("Project root:", PROJECT_ROOT)
    print("Raw directory:", RAW_DIR)

    blocks_23501 = parse_3gpp_document(doc_23501, "TS 23.501", "18")
    blocks_24501 = parse_3gpp_document(doc_24501, "TS 24.501", "18")

    all_blocks = blocks_23501 + blocks_24501
    output_file = PROCESSED_DIR / "parsed_blocks.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_blocks, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
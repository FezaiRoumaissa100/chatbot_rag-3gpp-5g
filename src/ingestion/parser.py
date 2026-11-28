import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.corpus import discover_specs, write_manifest

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SECTION_RE = re.compile(r'^(\d+(?:\.\d+)*[a-zA-Z]?)\s+(.*)')


def table_to_text(table: Table) -> str:
    """Rows joined with ' | '. Horizontally merged cells are emitted once."""
    rows = []
    for row in table.rows:
        cells, prev = [], None
        for cell in row.cells:
            if prev is not None and cell._tc is prev:
                continue
            prev = cell._tc
            cells.append(cell.text.strip().replace("\n", " "))
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def parse_3gpp_document(file_path: Path, specification: str, release: str, version: str) -> list[dict]:
    """Parses a 3GPP .docx sequentially (skips cover, TOC and change history)."""
    print(f"\nParsing {specification} Rel-{release} ({version})...")
    doc = Document(file_path)
    blocks, capture, heading_stack = [], False, {}
    current_section = current_title = ""

    def base(kind: str, text: str, style: str = "") -> dict:
        path = " > ".join(heading_stack[l] for l in sorted(heading_stack))
        d = {"type": kind, "text": text, "specification": specification, "release": release,
             "version": version, "section": current_section, "title": current_title, "hierarchy": path}
        if style:
            d["style"] = style
        return d

    for element in doc.element.body.iterchildren():
        if isinstance(element, CT_P):
            p = Paragraph(element, doc)
            text = p.text.strip()
            if not text:
                continue
            style = p.style.name if p.style else ""
            if style == "Heading 1" and "Foreword" in text:
                capture = True
            if not capture:
                continue
            if style == "Heading 1" and "Change history" in text:
                break
            if style.startswith("Heading"):
                try:
                    level = int(style.replace("Heading", "").strip())
                except ValueError:
                    level = None
                if level is not None:
                    heading = text.replace("\n", " ")
                    heading_stack[level] = heading
                    for key in [k for k in heading_stack if k > level]:
                        del heading_stack[key]
                    m = SECTION_RE.match(heading)
                    if m:
                        current_section, current_title = m.group(1), m.group(2).strip()
                    else:
                        current_section, current_title = heading.split(":")[0].strip(), heading
                continue
            if style == "TF":
                continue
            blocks.append(base("paragraph", text, style))
        elif isinstance(element, CT_Tbl) and capture:
            text = table_to_text(Table(element, doc))
            if text.strip():
                blocks.append(base("table", text))

    print(f"  blocks: {len(blocks)}")
    return blocks


def main():
    files = discover_specs()
    if not files:
        raise SystemExit("No matching .docx found in data/raw (expected TS_23.501_V18.12.0.docx ...)")
    write_manifest(files)
    all_blocks = []
    for f in files:
        all_blocks += parse_3gpp_document(f.path, f.specification, f.release, f.version)
    out = PROCESSED_DIR / "parsed_blocks.json"
    out.write_text(json.dumps(all_blocks, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(all_blocks)} blocks -> {out}")


if __name__ == "__main__":
    main()

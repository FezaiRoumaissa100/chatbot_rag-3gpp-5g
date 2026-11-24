import json
import re
from pathlib import Path
from collections import defaultdict

# ============================================================
# 1. CONFIGURATION & PARAMETERS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_FILE = PROCESSED_DIR / "parsed_blocks.json"
OUTPUT_FILE = PROCESSED_DIR / "chunks.json"

# Chunk size thresholds in characters (~150-250 words, safely under 512 tokens)
TARGET_CHUNK_SIZE = 1000
MAX_CHUNK_SIZE = 1600
MAX_OVERLAP_CHARS = 350


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def build_context_header(spec: str, release: str, section: str, title: str) -> str:
    """Creates a standardized metadata prefix injected into every chunk."""
    if section == title:
        return f"[{spec} | Release {release} | Section {section}]"
    return f"[{spec} | Release {release} | Section {section} - {title}]"


def sanitize_id(text: str) -> str:
    """Cleans strings to build safe, readable chunk identifiers."""
    return re.sub(r'[^a-zA-Z0-9\._-]', '_', text).strip('_')


def hard_split_text(text: str, max_len: int) -> list[str]:
    """Splits a string into pieces strictly <= max_len along word boundaries."""
    if max_len <= 0:
        return [text[:100]]
    words = text.split(" ")
    parts = []
    current = ""

    for word in words:
        if len(word) > max_len:
            if current:
                parts.append(current)
                current = ""
            for i in range(0, len(word), max_len):
                parts.append(word[i:i + max_len])
        elif len(current) + len(word) + (1 if current else 0) > max_len:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word

    if current:
        parts.append(current)
    return parts


def split_large_table(table_text: str, available_size: int) -> list[str]:
    """
    Splits an oversized table by rows while repeating the header row
    at the top of every sub-chunk, guaranteeing every sub-chunk <= available_size.
    """
    rows = table_text.split("\n")
    if len(rows) <= 1:
        return hard_split_text(table_text, available_size)

    header = rows[0]
    max_header_len = max(100, available_size // 3)
    if len(header) > max_header_len:
        header = header[:max_header_len - 3] + "..."

    data_rows = rows[1:]
    sub_tables = []
    current_rows = [header]
    current_len = len(header)
    max_row_budget = available_size - len(header) - 1

    for row in data_rows:
        # Fallback split if a single merged table row is excessively long
        if len(row) > max_row_budget:
            if len(current_rows) > 1:
                sub_tables.append("\n".join(current_rows))
                current_rows = [header]
                current_len = len(header)
            for row_part in hard_split_text(row, max_row_budget):
                sub_tables.append(f"{header}\n{row_part}")
            continue

        row_len = len(row) + 1
        if current_len + row_len > available_size and len(current_rows) > 1:
            sub_tables.append("\n".join(current_rows))
            current_rows = [header, row]
            current_len = len(header) + row_len
        else:
            current_rows.append(row)
            current_len += row_len

    if len(current_rows) > 1:
        sub_tables.append("\n".join(current_rows))

    return sub_tables


def split_large_paragraph(text: str, available_size: int) -> list[str]:
    """Splits an unusually long single paragraph along sentence or word boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    parts = []
    current_part = ""

    for sentence in sentences:
        if len(sentence) > available_size:
            if current_part:
                parts.append(current_part.strip())
                current_part = ""
            parts.extend(hard_split_text(sentence, available_size))
        elif len(current_part) + len(sentence) + 1 > available_size and current_part:
            parts.append(current_part.strip())
            current_part = sentence
        else:
            current_part = f"{current_part} {sentence}".strip() if current_part else sentence

    if current_part:
        parts.append(current_part.strip())

    return parts


# ============================================================
# 3. STRUCTURAL CHUNKING ENGINE
# ============================================================

def create_structural_chunks(blocks: list[dict]) -> list[dict]:
    """
    Groups parsed blocks into semantically coherent chunks while strictly
    respecting section boundaries and protecting table structures.
    """
    chunks = []
    section_counters = defaultdict(int)

    buffer_blocks = []
    buffer_len = 0
    has_new_content = False
    current_meta = None

    def flush_buffer(keep_overlap: bool = False):
        nonlocal buffer_blocks, buffer_len, has_new_content

        # Avoid emitting a standalone duplicate chunk if buffer only holds overlap text
        if not buffer_blocks or not has_new_content or current_meta is None:
            buffer_blocks = []
            buffer_len = 0
            has_new_content = False
            return

        spec = current_meta["specification"]
        release = current_meta["release"]
        section = current_meta["section"]
        title = current_meta["title"]
        hierarchy = current_meta["hierarchy"]

        header = build_context_header(spec, release, section, title)
        body_text = "\n".join(b["text"] for b in buffer_blocks)
        full_text = f"{header}\n{body_text}"

        key = f"{sanitize_id(spec)}_{sanitize_id(section)}"
        section_counters[key] += 1
        chunk_id = f"{key}_{section_counters[key]:04d}"

        has_table = any(b["type"] == "table" for b in buffer_blocks)

        chunks.append({
            "chunk_id": chunk_id,
            "specification": spec,
            "release": release,
            "section": section,
            "title": title,
            "hierarchy": hierarchy,
            "has_table": has_table,
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
            "text": full_text
        })

        # Intra-section overlap: keep last short paragraph only if more blocks follow
        if keep_overlap and buffer_blocks:
            last_block = buffer_blocks[-1]
            if last_block["type"] == "paragraph" and len(last_block["text"]) <= MAX_OVERLAP_CHARS:
                buffer_blocks = [last_block]
                buffer_len = len(last_block["text"])
                has_new_content = False
                return

        buffer_blocks = []
        buffer_len = 0
        has_new_content = False

    for block in blocks:
        spec = block["specification"]
        section = block["section"]
        block_text = block["text"].strip()
        block_type = block["type"]
        block_style = block.get("style", "")

        if not block_text:
            continue

        is_new_section = (
            current_meta is None
            or spec != current_meta["specification"]
            or section != current_meta["section"]
        )

        if is_new_section:
            flush_buffer(keep_overlap=False)
            current_meta = {
                "specification": spec,
                "release": block["release"],
                "section": section,
                "title": block["title"],
                "hierarchy": block["hierarchy"]
            }

        header_len = len(build_context_header(
            current_meta["specification"],
            current_meta["release"],
            current_meta["section"],
            current_meta["title"]
        )) + 1
        available_for_body = MAX_CHUNK_SIZE - header_len

        # Handle oversized single blocks (large NAS tables or giant paragraphs)
        if len(block_text) > available_for_body:
            flush_buffer(keep_overlap=False)

            if block_type == "table":
                sub_parts = split_large_table(block_text, available_for_body)
            else:
                sub_parts = split_large_paragraph(block_text, available_for_body)

            for part in sub_parts:
                buffer_blocks = [{"type": block_type, "style": block_style, "text": part}]
                buffer_len = len(part)
                has_new_content = True
                flush_buffer(keep_overlap=False)
            continue

        projected_len = header_len + buffer_len + len(block_text) + (1 if buffer_blocks else 0)

        if projected_len > MAX_CHUNK_SIZE and buffer_blocks:
            flush_buffer(keep_overlap=True)

            rechecked_len = header_len + buffer_len + len(block_text) + (1 if buffer_blocks else 0)
            if rechecked_len > MAX_CHUNK_SIZE:
                buffer_blocks = []
                buffer_len = 0
                has_new_content = False

        buffer_blocks.append({
            "type": block_type,
            "style": block_style,
            "text": block_text
        })
        buffer_len += len(block_text) + (1 if len(buffer_blocks) > 1 else 0)
        has_new_content = True

        if (header_len + buffer_len) >= TARGET_CHUNK_SIZE and block_style != "TH":
            flush_buffer(keep_overlap=True)

    flush_buffer(keep_overlap=False)
    return chunks


# ============================================================
# 4. MAIN EXECUTION & SUMMARY STATS
# ============================================================

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Parsed blocks file not found: {INPUT_FILE}")

    print(f"Loading parsed blocks from {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        blocks = json.load(f)

    print(f"Total input blocks: {len(blocks)}")
    chunks = create_structural_chunks(blocks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    by_spec = defaultdict(list)
    for c in chunks:
        by_spec[c["specification"]].append(c)

    print("\n====================================================")
    print("STRUCTURAL CHUNKING COMPLETED")
    print("====================================================")
    print(f"Total chunks generated : {len(chunks)}")
    print(f"Output saved to        : {OUTPUT_FILE}\n")

    for spec, spec_chunks in by_spec.items():
        char_counts = [c["char_count"] for c in spec_chunks]
        table_chunks = sum(1 for c in spec_chunks if c["has_table"])
        avg_chars = sum(char_counts) / len(char_counts)
        print(f"--- {spec} ---")
        print(f"  Chunks count     : {len(spec_chunks)}")
        print(f"  Chunks w/ tables : {table_chunks}")
        print(f"  Avg length       : {avg_chars:.0f} chars")
        print(f"  Min / Max length : {min(char_counts)} / {max(char_counts)} chars\n")


if __name__ == "__main__":
    main()
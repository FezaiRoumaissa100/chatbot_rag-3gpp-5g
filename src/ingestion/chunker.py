import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cfg

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
INPUT_FILE = PROCESSED_DIR / "parsed_blocks.json"
OUTPUT_FILE = PROCESSED_DIR / "chunks.json"

TARGET_CHUNK_SIZE = cfg("chunking")["target_chars"]
MAX_CHUNK_SIZE = cfg("chunking")["max_chars"]
MAX_OVERLAP_CHARS = cfg("chunking")["overlap_chars"]


def build_context_header(spec: str, release: str, section: str, title: str) -> str:
    if section == title:
        return f"[{spec} | Release {release} | Section {section}]"
    return f"[{spec} | Release {release} | Section {section} - {title}]"


def sanitize_id(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\._-]', '_', text).strip('_')


def hard_split_text(text: str, max_len: int) -> list[str]:
    if max_len <= 0:
        return [text[:100]]
    parts, current = [], ""
    for word in text.split(" "):
        if len(word) > max_len:
            if current:
                parts.append(current)
                current = ""
            parts.extend(word[i:i + max_len] for i in range(0, len(word), max_len))
        elif len(current) + len(word) + (1 if current else 0) > max_len:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        parts.append(current)
    return parts


def split_large_table(table_text: str, available: int) -> list[str]:
    """Splits by rows, repeating the header row in every sub-chunk."""
    rows = table_text.split("\n")
    if len(rows) <= 1:
        return hard_split_text(table_text, available)
    header = rows[0]
    max_header = max(100, available // 3)
    if len(header) > max_header:
        header = header[:max_header - 3] + "..."
    subs, cur, cur_len = [], [header], len(header)
    row_budget = available - len(header) - 1
    for row in rows[1:]:
        if len(row) > row_budget:
            if len(cur) > 1:
                subs.append("\n".join(cur))
                cur, cur_len = [header], len(header)
            subs.extend(f"{header}\n{part}" for part in hard_split_text(row, row_budget))
            continue
        row_len = len(row) + 1
        if cur_len + row_len > available and len(cur) > 1:
            subs.append("\n".join(cur))
            cur, cur_len = [header, row], len(header) + row_len
        else:
            cur.append(row)
            cur_len += row_len
    if len(cur) > 1:
        subs.append("\n".join(cur))
    return subs


def split_large_paragraph(text: str, available: int) -> list[str]:
    parts, cur = [], ""
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if len(sentence) > available:
            if cur:
                parts.append(cur.strip())
                cur = ""
            parts.extend(hard_split_text(sentence, available))
        elif len(cur) + len(sentence) + 1 > available and cur:
            parts.append(cur.strip())
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip() if cur else sentence
    if cur:
        parts.append(cur.strip())
    return parts


def create_structural_chunks(blocks: list[dict]) -> list[dict]:
    chunks, counters = [], defaultdict(int)
    buf, buf_len, has_new, meta = [], 0, False, None

    def flush(keep_overlap: bool = False):
        nonlocal buf, buf_len, has_new
        if not buf or not has_new or meta is None:
            buf, buf_len, has_new = [], 0, False
            return
        header = build_context_header(meta["specification"], meta["release"], meta["section"], meta["title"])
        full = f"{header}\n" + "\n".join(b["text"] for b in buf)
        key = f"{sanitize_id(meta['specification'])}_R{meta['release']}_{sanitize_id(meta['section'])}"
        counters[key] += 1
        chunks.append({
            "chunk_id": f"{key}_{counters[key]:04d}",
            "specification": meta["specification"], "release": meta["release"],
            "version": meta.get("version", ""), "section": meta["section"], "title": meta["title"],
            "hierarchy": meta["hierarchy"], "has_table": any(b["type"] == "table" for b in buf),
            "char_count": len(full), "word_count": len(full.split()), "text": full,
        })
        if keep_overlap and buf:
            last = buf[-1]
            if last["type"] == "paragraph" and len(last["text"]) <= MAX_OVERLAP_CHARS:
                buf, buf_len, has_new = [last], len(last["text"]), False
                return
        buf, buf_len, has_new = [], 0, False

    for block in blocks:
        text, btype, style = block["text"].strip(), block["type"], block.get("style", "")
        if not text:
            continue
        new_section = (meta is None or block["specification"] != meta["specification"]
                       or block["release"] != meta["release"] or block["section"] != meta["section"])
        if new_section:
            flush(False)
            meta = {k: block.get(k, "") for k in
                    ("specification", "release", "version", "section", "title", "hierarchy")}

        header_len = len(build_context_header(meta["specification"], meta["release"],
                                              meta["section"], meta["title"])) + 1
        available = MAX_CHUNK_SIZE - header_len

        if len(text) > available:
            flush(False)
            subs = split_large_table(text, available) if btype == "table" else split_large_paragraph(text, available)
            for part in subs:
                buf, buf_len, has_new = [{"type": btype, "style": style, "text": part}], len(part), True
                flush(False)
            continue

        if header_len + buf_len + len(text) + (1 if buf else 0) > MAX_CHUNK_SIZE and buf:
            flush(True)
            if header_len + buf_len + len(text) + (1 if buf else 0) > MAX_CHUNK_SIZE:
                buf, buf_len, has_new = [], 0, False

        buf.append({"type": btype, "style": style, "text": text})
        buf_len += len(text) + (1 if len(buf) > 1 else 0)
        has_new = True
        if (header_len + buf_len) >= TARGET_CHUNK_SIZE and style != "TH":
            flush(True)

    flush(False)
    return chunks


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Run the parser first: {INPUT_FILE}")
    blocks = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    print(f"Input blocks: {len(blocks)}")
    chunks = create_structural_chunks(blocks)
    OUTPUT_FILE.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    by = defaultdict(list)
    for c in chunks:
        by[(c["specification"], c["release"], c["version"])].append(c)
    print(f"\nTotal chunks: {len(chunks)}  ->  {OUTPUT_FILE}\n")
    for (spec, rel, ver), cs in sorted(by.items()):
        n = [c["char_count"] for c in cs]
        print(f"{spec} Rel-{rel} ({ver}): {len(cs)} chunks, {sum(c['has_table'] for c in cs)} with tables, "
              f"avg {sum(n)/len(n):.0f} chars, max {max(n)}")


if __name__ == "__main__":
    main()

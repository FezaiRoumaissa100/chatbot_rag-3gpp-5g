"""Corpus discovery: finds every 3GPP .docx in data/raw and records spec/release/version.

File naming convention (rename the downloaded files once):
    TS_23.501_V18.12.0.docx   ->  TS 23.501, Release 18, version V18.12.0
    TS_24.501_V17.13.0.docx   ->  TS 24.501, Release 17, version V17.13.0
The major version number of a 3GPP spec IS its release number (from Rel-15 on).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import cfg

FILE_RE = re.compile(r"TS[_\s-]?(\d{2}\.\d{3})[_\s-]?V(\d+)\.(\d+)\.(\d+)\.docx$", re.IGNORECASE)
MANIFEST = PROJECT_ROOT / "data" / "processed" / "corpus_manifest.json"


@dataclass
class SpecFile:
    specification: str
    release: str
    version: str
    path: Path
    key: tuple = ()


def discover_specs(raw_dir: Path | None = None) -> list[SpecFile]:
    raw_dir = raw_dir or (PROJECT_ROOT / cfg("corpus")["raw_dir"])
    enabled = set(cfg("corpus")["specs"])
    best: dict[tuple[str, str], SpecFile] = {}
    for p in sorted(raw_dir.glob("*.docx")):
        m = FILE_RE.search(p.name)
        if not m:
            print(f"  (skipped, name does not match TS_xx.xxx_Vm.n.p.docx): {p.name}")
            continue
        spec, major, minor, patch = f"TS {m.group(1)}", int(m.group(2)), int(m.group(3)), int(m.group(4))
        if spec not in enabled:
            continue
        sf = SpecFile(spec, str(major), f"V{major}.{minor}.{patch}", p, (major, minor, patch))
        k = (spec, sf.release)
        if k not in best or sf.key > best[k].key:   # keep the newest version of a release
            best[k] = sf
    return sorted(best.values(), key=lambda s: (s.specification, s.release))


def write_manifest(files: list[SpecFile]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    data = [{"specification": f.specification, "release": f.release, "version": f.version,
             "file": f.path.name} for f in files]
    MANIFEST.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    files = discover_specs()
    for f in files:
        print(f"{f.specification:10s} Rel-{f.release}  {f.version:10s} {f.path.name}")
    if not files:
        print("No spec found in data/raw")

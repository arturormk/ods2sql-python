#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parents[1] / "docs" / "adr"

REQ_SECTIONS = ("## Context", "## Decision", "## Consequences")

def main() -> int:
    if not ADR_DIR.is_dir():
        print("ADR directory not found", file=sys.stderr)
        return 1
    ok = True
    rx = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
    for p in sorted(ADR_DIR.glob("*.md")):
        if p.name in {"README.md", "TEMPLATE.md"}:
            continue
        if not rx.match(p.name):
            print(f"[ADR LINT] Bad filename: {p.name} (expected 0000-title.md)", file=sys.stderr)
            ok = False
        text = p.read_text(encoding="utf-8")
        for sec in REQ_SECTIONS:
            if sec not in text:
                print(f"[ADR LINT] Missing section {sec} in {p.name}", file=sys.stderr)
                ok = False
    return 0 if ok else 2

if __name__ == "__main__":
    sys.exit(main())

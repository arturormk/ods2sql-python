#!/usr/bin/env python3
"""Lint curatorial incident log entries.

Checks:
- Directory exists: docs/incidents
- Files follow naming: INC-XXXX-*.md (XXXX numeric, zero-padded)
- IDs strictly sequential without gaps.
- Each file contains required section headings:
    ## Context / Trigger
    ## Symptom
    ## Root Cause
    ## Resolution
    ## Prevention / Guardrail
    ## References
- Status line present near top: **Status:**
- Tags line present: **Tags:**
- If Closed, must mention at least one commit hash pattern (7+ hex) in body.
Exit non-zero on failure.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import NoReturn

RE_FILE = re.compile(r'^INC-(\d{4})-[a-z0-9-]+\.md$')
RE_COMMIT = re.compile(r'\b[0-9a-f]{7,40}\b')
RE_REQUIRED_SECTIONS = [
    '## Context / Trigger',
    '## Symptom',
    '## Root Cause',
    '## Resolution',
    '## Prevention / Guardrail',
    '## References',
]

RE_STATUS = re.compile(r'^\*\*Status:\*\*\s*(.+)$', re.IGNORECASE)
RE_TAGS = re.compile(r'^\*\*Tags:\*\*\s*(.+)$', re.IGNORECASE)


def fail(msg: str) -> NoReturn:
    print(f'[INC-LINT] FAIL: {msg}', file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    idir = root / 'docs' / 'incidents'
    if not idir.exists():
        print('[INC-LINT] No incidents directory (skip).')
        return 0
    files = [p for p in idir.glob('INC-*.md') if p.is_file() and p.name != 'TEMPLATE.md']
    if not files:
        print('[INC-LINT] No incident files.')
        return 0
    files.sort()
    ids: list[int] = []
    for p in files:
        m = RE_FILE.match(p.name)
        if not m:
            fail(f'Bad filename: {p.name} (expected INC-XXXX-kebab.md)')
        g = m.group(1)
        ids.append(int(g))
    # Check sequential
    for previous, current in zip(ids, ids[1:]):
        if current != previous + 1:
            fail(f'ID gap between {previous:04d} and {current:04d}')
    # Lint content
    for p in files:
        text = p.read_text(encoding='utf-8')
        # Headings
        for sec in RE_REQUIRED_SECTIONS:
            if sec not in text:
                fail(f"Missing section '{sec}' in {p.name}")
        # Status & Tags near top (first 25 lines)
        lines = text.splitlines()[:25]
        status = any(RE_STATUS.search(line) for line in lines)
        tags = any(RE_TAGS.search(line) for line in lines)
        if not status:
            fail(f'Missing **Status:** line near top of {p.name}')
        if not tags:
            fail(f'Missing **Tags:** line near top of {p.name}')
        if '**Status:** Closed' in text:
            if not RE_COMMIT.search(text):
                fail(f'Closed incident {p.name} missing commit reference')
    print('[INC-LINT] OK: incidents lint passed.')
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())

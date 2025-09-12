#!/usr/bin/env python3
"""Ensure docs/adr/README.md index lists the highest-numbered ADR present.

Policy: every ADR file 000N-*.md must appear as a line in the index.
Exit 1 if mismatch so pre-commit blocks.
"""
from __future__ import annotations
import re
from pathlib import Path
import sys

ADR_DIR = Path('docs/adr')
INDEX_FILE = ADR_DIR / 'README.md'

rx = re.compile(r'^(\d{4})-([a-z0-9-]+)\.md$')

missing: list[str] = []
try:
    index_text = INDEX_FILE.read_text(encoding='utf-8')
except FileNotFoundError:
    print('ADR index missing', file=sys.stderr)
    sys.exit(1)

for p in sorted(ADR_DIR.glob('*.md')):
    if p.name in {'README.md', 'TEMPLATE.md'}:
        continue
    if not rx.match(p.name):
        print(f'Bad ADR filename: {p.name}', file=sys.stderr)
        sys.exit(1)
    if p.name not in index_text:
        missing.append(p.name)

if missing:
    print('ADR index missing entries for: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)

sys.exit(0)

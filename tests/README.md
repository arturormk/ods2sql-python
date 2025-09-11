# Test Guide for `ods2sql-python`

This suite verifies the CLI contract, parser edge cases, and SQL emission across dialects. It favors **behavioral confidence** over 100% coverage.

## How to run

### Create virtual environment

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip pytest
```

### Run tests

```bash
python -m pytest -q
# subsets:
python -m pytest -q tests/test_sqlite_roundtrip.py::test_roundtrip_sqlite
python -m pytest -m "not slow"
```

CI runs these tests on each push/PR (see `.github/workflows/ci.yml`).

## Structure 

```
tests/
  README.md                # this file
  helpers.py               # tiny ODS generator (zip + content.xml)
  test_sqlite_roundtrip.py # integration tests (SQLite)
  test_parser_edges.py     # ODS parsing semantics & markers
  test_dialects.py         # emitted SQL differences by dialect
  test_cli_contract.py     # exit codes, stdout/stderr, flags
```

## Fixtures

- Prefer programmatic ODS via helpers.py (fast, tiny, precise).
- Check in 1–2 real .ods samples only if needed for human inspection.

## Test Matrix

Note: This matrix also guides automated test scaffolding that synthesizes or updates test cases. Keep it accurate and action-oriented so tools can generate reliable, minimal tests that reflect the intended behavior.

### A. Integration (SQLite)
- A1 Happy path: one table, types, 5 rows → DB loads, COUNT(*) correct.
- A2 Schema/Data split: --schema-only then --data-only → ok.
- A3 Batching/Transaction: --transaction --batch 2 → ok.
- A4 PK & indexes: --primary-key id; per-column indexes exist (non-PK).
- A5 Table filter: multiple tables; --table foo only emits foo.

### B. Parser behavior
- B1 Scanning: text above control rows; find first sqltable.
- B2 Aliases: columns/column/fields and types/type accepted.
- B3 Duplicates: duplicate column names → fail fast (ODSParseError).
- B4 Repetition: number-columns-repeated, number-rows-repeated expand correctly.
- B5 Covered cells: merged cells read as NULL.
- B6 Empty strings: '' emitted as NULL.
- B7 Comments: only first-cell comment is ignored.

### C. Dialect emission (string-level)
- C1 Quoting: sqlite/postgres use "..."; mysql uses `...`.
- C2 Booleans: sqlite 1/0; Postgres/MySQL TRUE/FALSE.
- C3 Identifier length: index names ≤ limit; truncated + hash suffix.
- C4 MySQL TEXT/BLOB: index creation skipped with warning.

### D. CLI contract
- D1 Exit codes: bad file → 2; no instrumented tables → 0 with [WARN].
- D2 Streams: SQL only on stdout; diagnostics on stderr.
- D3 Dialect alias: --dialect postgresql accepted.

## Conventions
- Don’t import ods2sql.py in tests; call it via subprocess to test the CLI contract.
- Keep tests tiny and deterministic; avoid sleeping or randomness.
- Name tests by behavior (e.g., test_duplicate_columns_fail_fast).

## Pytest markers

Register common markers in `pytest.ini`:

```
# pytest.ini
[pytest]
addopts = -q
markers =
    slow: long-running tests
    sqliteonly: requires sqlite execution (default)
```

Usage: `pytest -m "not slow"`.

## Helpers

`tests/helpers.py` provides:
- `write_ods(path, sheet_name, rows)` — build a minimal `.ods` with namespaced `content.xml`.
- `make_row`/`make_cell` utilities for `value-type`, repetition, and covered cells.

Use these to synthesize edge cases precisely.

## References
- ADR-0004: Type coercion & NULL semantics
- ADR-0007: Transactions & batching
- ADR-0008: Duplicate column names fail fast
- ADR-0009: Output contract (stdout vs stderr) & versioning

# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog and uses semantic-ish versioning (major.minor.patch).

## [0.1.1] - 2025-10-19
Enhancements:
- TEXT columns now prefer the document’s own display text, preserving locale formatting (e.g., commas and non‑breaking space before %).
- Percentage fallback for TEXT cells (when no display text is present) reads decimal places from content.xml styles; otherwise rounds sensibly and trims trailing zeros. Locale decimal separator is respected where applicable.

Developer experience:
- Added Development setup instructions (venv + requirements-dev.txt).
- mypy --strict clean: added annotations across test helpers and scripts.

Docs:
- Updated ADR-0004 and README to mention TEXT formatted display semantics.

## [0.1.0] - 2025-11-09
Initial curated release.

Highlights:
- Pure-stdlib ODS parser (zipfile + xml.etree) with multi-sheet, multi-table extraction.
- Dialect-aware SQL emission (sqlite, postgres/postgresql, mysql) including quoting & booleans.
- Automatic per-column indexes (configurable / disable-able) plus composite index support.
- PRIMARY KEY handling with redundant index suppression.
- MySQL TEXT/BLOB index skipping with warnings.
- Empty string → NULL normalization and numeric/boolean/date inference.
- Identifier length limiting with deterministic hash suffix.
- CLI batching of INSERT statements and optional single-transaction output.
- Robust warnings for malformed instrumentation plus fail-fast on duplicate column names.
- ADR-driven architecture documentation & AI curation policy.
- Pre-commit quality gates (Ruff lint/format, fast tests, ADR index sync, print guard).
- GitHub Actions CI matrix (3.9–3.12) for lint, type check, tests, build.

### Packaging Note
The dynamic version attribute configuration was replaced with a static `version = "0.1.0"` in `pyproject.toml` to resolve a CI build metadata resolution error. The module constant `__version__` remains for runtime visibility.

---

Future entries will document incremental improvements and bug fixes.

# ods2sql-python 0.1.1 — 2025-10-19

Enhancements:
- TEXT columns now prefer the document’s own display text, preserving locale formatting (e.g., commas and non‑breaking space before %).
- Percentage fallback for TEXT cells (when no display text is present) reads decimal places from content.xml styles; otherwise rounds sensibly and trims trailing zeros. Locale decimal separator is respected where applicable.

Developer experience:
- Added Development setup instructions (venv + requirements-dev.txt).
- mypy --strict clean: added annotations across test helpers and scripts.

Docs:
- Updated ADR-0004 and README to mention TEXT formatted display semantics.

Tag: v0.1.1

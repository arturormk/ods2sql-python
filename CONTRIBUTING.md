# Contributing

Thanks for your interest in improving this project. This repository doubles as a template to model a “Software Curator” posture: small, well-tested, well-documented, and automation-friendly.

- Use Python 3.9+
- Run tests locally before committing: `pytest -q`
- Lint: `ruff check .` and fix reported issues
- Type check: `mypy --strict src tests scripts`
- Keep changes focused and add tests for behavior changes
- If you change user-visible behavior, consider adding/updating an ADR in `docs/adr/`

## Development quickstart

1. Create a virtualenv and install dev deps
2. Run tests and linters
3. Make changes in `src/`
4. Add or update tests in `tests/`

## Releasing

- Version is defined in `src/ods2sql.py` (`__version__`), and used dynamically by `pyproject.toml`.
- Tag as `vX.Y.Z` and push tags. Consider creating a GitHub Release with notes.

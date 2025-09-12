# INC-0001 — Dynamic Version Resolution Failure

**Status:** Closed
**Date:** 2025-09-12
**Tags:** ci, packaging, build, governance

## Context / Trigger
Introduced dynamic versioning in `pyproject.toml` using:
```
[tool.setuptools.dynamic]
version = { attr = "ods2sql:__version__" }
```
with a single-module layout (`src/ods2sql.py`) declared via `[tool.setuptools] py-modules = ["ods2sql"]`.
CI (GitHub Actions build matrix Python 3.9–3.12) began failing during the build phase after adding packaging metadata.

## Symptom
Setuptools configuration error:
```
configuration error: tool.setuptools.dynamic.version must be valid exactly by one definition (0 matches found)
```
Failing early in the build step; tests/lint not reached.

## Root Cause
Setuptools dynamic attribute resolution did not locate `__version__` in the isolated build environment when using the single-file `py-modules` layout. While the attribute exists (`__version__ = "0.1.0"` in `src/ods2sql.py`), the dynamic resolution path proved brittle (likely due to how the isolated backend environment imports modules before writing metadata). This fragility surfaced only in CI, not in quick local checks.

## Resolution
Replaced dynamic version block with a static version field:
```
[project]
version = "0.1.0"
```
Removed `[tool.setuptools.dynamic]` section. Retained `__version__` constant in the module for runtime introspection and `--version` CLI flag. Commit: `cefa34b` ("Packaging: set static version; add CHANGELOG and CITATION").

## Prevention / Guardrail
- Policy: Prefer static `version` field for single-module distributions unless migrating to a package directory (`src/ods2sql/__init__.py`).
- If dynamic versioning is reconsidered, add a CI step: import the module inside the isolated build env and assert printed `__version__` matches `pyproject.toml`.
- Documented here; CHANGELOG entry notes packaging adjustment.

## References
- Commit: cefa34b
- ADR: 0009 (Output contract & versioning) – remains valid; this incident adds a constraint (static version for simplicity).
- CI failing run: (link to run inserting error message) [ADD LINK IF NEEDED]

## Notes / Future Considerations
If/when project evolves into a multi-file package, we can centralize version in `src/ods2sql/__init__.py` and optionally re-enable dynamic versioning with a verification step. Until then, static versioning minimizes moving parts in release automation.

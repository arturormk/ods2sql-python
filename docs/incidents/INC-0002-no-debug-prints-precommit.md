# INC-0002 — Pre-commit failure: Disallow raw print without file=

**Status:** Closed
**Date:** 2025-10-19
**Tags:** tooling, hooks, DX

## Context / Trigger
While preparing the 0.1.1 release, we added docs/tests and small refactors to `src/ods2sql.py`. The repository enforces a custom pre-commit hook (`scripts/check_prints.sh`) that fails if any `print(` call appears without an explicit `file=` parameter in `src/ods2sql.py`. This is part of our output contract: only SQL goes to stdout; diagnostics must go to stderr.

## Symptom
Pre-commit blocked the commit with:
```
Disallow raw print without file= in src..................................Failed
- hook id: no-debug-prints
- exit code: 1

Found raw print() without file= parameter in src/ods2sql.py. Use file=stderr or file=out.
```
However, manual inspection suggested we had already added `file=...` to our prints, which caused confusion.

## Root Cause
The check script is a simple grep that looks for lines where `print(` appears without `file=` on the same line. Multi-line `print(` calls (where arguments are line-wrapped and `file=` is on a subsequent line) trigger a false-positive. Additionally, the formatter (ruff-format) can reflow prints into multi-line forms, re-triggering the hook even after fixes.

## Resolution
- Refactored long/multi-line `print(` calls to ensure `file=` appears on the same line as `print(`. Tactics used:
  - Assign long f-strings to a temporary variable `msg` and then `print(msg, file=sys.stderr)`.
  - For long expressions (e.g., create_index statements), assign to a local variable (e.g., `idx_stmt`) and then print with `file=out` in a single line.
- Verified the hook locally via `scripts/check_prints.sh` and ensured `ruff-format` does not reflow `print` calls into a multi-line form.

## Prevention / Guardrail
- Coding guideline: Always keep `file=` on the same line as `print(`. Prefer `msg = ...; print(msg, file=...)` for long content.
- Optional: Enhance `scripts/check_prints.sh` to parse multi-line calls or use a Python AST checker to reduce false-positives.
- CI/readme note: Explain why `file=` is required (stdout contract) and how the hook checks it.

## References
- Commit: 906dfa3 ("chore: add 0.1.1 release notes and finalize docs/tests for TEXT formatted output")
- Hook script: `scripts/check_prints.sh`
- File: `src/ods2sql.py`
- Release: v0.1.1 (commit includes these changes)

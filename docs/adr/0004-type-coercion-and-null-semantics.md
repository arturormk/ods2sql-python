## 0004 — Type Coercion & NULL Semantics

**Status:** Accepted
**Date:** 2025-09-10

### Context

ODS stores values with `office:value-type` and helpers. We need predictable SQL literals across dialects.

### Decision

* Map: `string→str`, `float/currency/percentage→Decimal`, `boolean→bool`, `date/time→ISO strings`, covered/empty→`None`.
* Emit: `None→NULL`; booleans as `1/0` (SQLite) or `TRUE/FALSE` (PG/MySQL); decimals as non-scientific; strings quoted with `''` escaping.
* **Empty strings (`''`) are emitted as `NULL`.**

### Consequences

* Stable round‑tripping for typical spreadsheets.
* Users wanting empty‑string vs NULL distinction must encode explicit markers.

### Alternatives

* Preserve empty string as `''` (risk of accidental empties from Calc formatting).
* Parse date/time into native SQL types (varies by dialect; out of scope for v0.1.0).

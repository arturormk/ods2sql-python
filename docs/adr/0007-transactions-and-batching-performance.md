## 0007 — Transactions & Batching (Performance)

**Status:** Accepted
**Date:** 2025-09-10

### Context

Large data loads are slow without batching and transactions, especially in SQLite.

### Decision

* `--batch N` to group rows into multi‑VALUES INSERTs (default 500).
* Optional `--transaction` to wrap output in a single `BEGIN/COMMIT;` for SQLite/Postgres.
* Keep MySQL behavior unchanged (no implicit transaction wrapping).

### Consequences

* Significant speedups for bulk loads when enabled.
* Easy to reason about output: still valid SQL scripts.

### Alternatives

* Engine‑specific PRAGMAs (future opt‑in).

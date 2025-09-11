## 0005 — SQL Dialects, Quoting, and Identifiers

**Status:** Accepted
**Date:** 2025-09-10

### Context

We target SQLite, Postgres, and MySQL with minimal divergence.

### Decision

* Dialects: `sqlite` (default), `postgres` (alias: `postgresql`), `mysql`.
* Identifiers quoted: `"..."` for SQLite/Postgres; `` `...` `` for MySQL.
* Support schema-qualified names by quoting parts individually.
* Enforce identifier length limits per dialect (portable cap=64). When exceeded, truncate and append an 8‑char SHA‑1 suffix.

### Consequences

* Predictable quoting/compat across the three engines.
* Very low risk of index-name collisions.

### Alternatives

* No quoting (breaks for keywords/spaces).
* Hash-only names (ugly and opaque).

## 0006 — Indexing Policy & PK Interactions

**Status:** Accepted
**Date:** 2025-09-10

### Context

The tool creates a temporary, queryable artifact for ad‑hoc analysis; indexing by default is desirable.

### Decision

* Default: create a non-unique index on **every** non‑PK column.
* Options: `--no-indices`, `--index-columns`, repeated `--index` for composites.
* Skip indexes that duplicate the PRIMARY KEY.
* MySQL: skip indexes on `TEXT/BLOB` columns; warn.

### Consequences

* Fast exploration at the cost of larger artifacts and load time; acceptable for the tool’s purpose.

### Alternatives

* Opt‑in indexing only (worse UX for the primary use case).

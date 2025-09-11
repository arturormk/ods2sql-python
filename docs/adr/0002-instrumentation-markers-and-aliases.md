## 0002 — Instrumentation Markers and Aliases

**Status:** Accepted
**Date:** 2025-09-10

### Context

Users instrument sheets with a first column of control keywords to declare schema and data. Names must be memorable and stable, but we want some flexibility.

### Decision

Markers (case/space-insensitive in matching, except `comment`):

* `sqltable` — start a new table block; `B` cell holds table name.
* `sqlcolumn` **and** aliases `{columns, column, fields}` — declare column names.
* `sqltype` **and** aliases `{types, type}` — declare SQL types; blanks → `TEXT`.
* `comment` — rows to ignore (exact match only).

### Consequences

* Backward compatible with the original tool.
* Clear separation between presentation headers and schema columns.

### Alternatives

* Prefix namespace (e.g., `sql:*`) for all markers (maybe later if collisions appear).

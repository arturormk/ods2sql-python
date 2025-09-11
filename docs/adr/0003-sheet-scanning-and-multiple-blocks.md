## 0003 — Sheet Scanning & Multiple Blocks

**Status:** Accepted
**Date:** 2025-09-10

### Context

Users may have titles/notes above the control rows. Multiple tables can live on the same sheet.

### Decision

Search row-by-row for the first `sqltable`. A new `sqltable` starts a new block; intervening rows are ignored unless they’re `sqlcolumn`/`sqltype`/data within the active block. Data rows require empty control cell. Fully empty rows are skipped. Covered cells behave as empty.

### Consequences

* Robust to preambles and mixed content.
* Clear block lifecycle and flushing semantics.

### Alternatives

* Require `A1=sqltable` (too brittle).
* Require one table per sheet (limits utility).

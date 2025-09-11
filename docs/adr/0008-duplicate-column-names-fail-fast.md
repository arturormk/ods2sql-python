## 0008 — Duplicate Column Names: Fail Fast

**Status:** Accepted
**Date:** 2025-09-10

### Context

Duplicate column names create ambiguous schemas and DDL errors.

### Decision

Detect case‑insensitive duplicates in the `columns` row and raise `ODSParseError` with a clear message.

### Consequences

* Early, actionable feedback instead of cryptic SQL errors downstream.

### Alternatives

* Auto‑dedupe (`name`, `name_2`, …) as an opt‑in in a future release if requested.

# Architecture Decision Records (ADRs)

Project: **ods2sql-python**
Version: **v0.1.0**
Date: **2025-09-10**
Maintainer role: **Software Curator**

This folder documents the key architectural decisions for ods2sql-python. We follow a lightweight ADR style (inspired by Nygard/MADR). New decisions should be added as new, incrementally numbered files.

## Index

- 0000 — [Record architecture decisions](./0000-record-architecture-decisions.md)
- 0001 — [Parse ODS with stdlib (zipfile + etree)](./0001-parse-ods-with-stdlib-zipfile-etree.md)
- 0002 — [Instrumentation markers and aliases](./0002-instrumentation-markers-and-aliases.md)
- 0003 — [Sheet scanning and multiple blocks](./0003-sheet-scanning-and-multiple-blocks.md)
- 0004 — [Type coercion and NULL semantics](./0004-type-coercion-and-null-semantics.md)
- 0005 — [SQL dialects, quoting and identifiers](./0005-sql-dialects-quoting-and-identifiers.md)
- 0006 — [Indexing policy and PK interactions](./0006-indexing-policy-and-pk-interactions.md)
- 0007 — [Transactions and batching performance](./0007-transactions-and-batching-performance.md)
- 0008 — [Duplicate column names fail fast](./0008-duplicate-column-names-fail-fast.md)
- 0009 — [Output contract (stdout vs stderr) and versioning](./0009-output-contract-stdout-vs-stderr-and-versioning.md)
- 0010 — [AI assistance and curation policy](./0010-ai-assistance-and-curation-policy.md)

> **Workflow**
>
> 1. Add a new file using the next sequence number.
> 2. Use the template from `TEMPLATE.md`.
> 3. Status transitions: *Proposed → Accepted → Superseded*.

Tip: Reference ADR IDs in code comments and tests (e.g., “see ADR-0004”) to make the curator’s intent visible and discoverable.

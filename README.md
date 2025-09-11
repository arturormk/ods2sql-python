# ods2sql-python
[![CI](https://github.com/arturormk/ods2sql-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/arturormk/ods2sql-python/actions/workflows/ci.yml)

One-file, pure-stdlib Python tool that converts instrumented LibreOffice .ods sheets into SQL for SQLite/Postgres/MySQL.

This dependency-free CLI reads native LibreOffice Calc .ods files (via `zipfile` + `xml.etree`) and emits SQL you can pipe straight into your database. Instrument your sheet with a tiny first-column markup and get reproducible `CREATE TABLE`, `INSERT`, and index statements—perfect for quick ETL, data audits, and sharing spreadsheet data as a real database.

## Highlights

- Pure standard library (no external deps)
- Multiple sheets & multiple tables per sheet
- Column selection via a “columns row”; SQL types via a “types row” (defaults to TEXT)
- Dialects: SQLite (default), Postgres, MySQL (affects quoting & booleans)
- Fast batched INSERTs; `--schema-only`, `--data-only`, `--list`, `--table`
- Indexes by default (per-column), plus composite indexes and PRIMARY KEY support
- Emits SQL on stdout; diagnostics on stderr (pipe-safe)

DuckDB: The SQLite dialect output works well with DuckDB in practice.

## Instrumentation (per sheet/tab)

Column A is reserved for control keywords; data starts at column B. The sheet must begin with:

```
A1 = 'sqltable'   B1 = <table_name>
```

Later control rows accept synonyms:

- Row 2 (columns row): A2 = one of 'sqlcolumn', 'columns', 'column', 'fields'  → non-empty B2.. define column names
- Row 3 (types row):   A3 = one of 'sqltype', 'types', 'type'                  → non-empty B3.. define SQL types (blank → TEXT)

Any row whose first cell is 'comment' is ignored.

Data rows have an empty first cell (in column A). Fully empty data rows are skipped.

Multiple tables per sheet are supported; each new 'sqltable' row starts a new block.

## Quick start

```bash
./ods2sql.py data.ods | sqlite3 data.sqlite
./ods2sql.py data.ods --dialect postgres --batch 1000 > load.sql
```

## Indexing and keys

By default, the tool creates a non-unique index for every column (handy for browsing/search in SQLite). You can customize:

- `--no-indices`  — don’t create any indexes
- `--index-columns "c1,c2"` — only index those columns (instead of all)
- `--index "c1+c2"` — define a composite index; flag may repeat
- `--primary-key "c1[,c2,...]"` — set a PRIMARY KEY in `CREATE TABLE`; PK columns are not redundantly indexed

## Other options

- `--dialect {sqlite,postgres,mysql}` — quoting & boolean style (default: sqlite)
- `--if-not-exists` — use IF NOT EXISTS in CREATE TABLE/INDEX where supported
- `--no-drop` — don’t emit DROP TABLE IF EXISTS
- `--schema-only` / `--data-only` — only DDL or only INSERTs
- `--batch N` — rows per INSERT (0/1 means one row per statement)
- `--table NAME` — only export specific table(s) (flag may repeat)
- `--list` — list detected tables/columns to stderr and exit

## Notes

- The parser collapses repeated empty rows in ODS to avoid expanding millions of blank lines at the end of a sheet.
- Identifiers are quoted and escaped per dialect; you can use schema-qualified names (e.g., `schema.table`).

## Portability notes

- Identifier length limits: generated index names are truncated to fit common limits (Postgres 63, MySQL 64, SQLite treated as 64 for portability). A short hash suffix is added when truncation occurs.
- MySQL index constraints: indexes on `TEXT`/`BLOB` columns require a prefix length in MySQL. This tool skips such indexes and prints a warning to stderr to avoid invalid SQL. Define composite indexes that avoid `TEXT`/`BLOB` columns, or add indexes manually with a prefix length if needed.
- Empty strings: empty Python strings (`""`) are emitted as SQL `NULL` values unconditionally.

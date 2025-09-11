# Examples for `ods2sql-python`

This folder contains small, instrumented LibreOffice `.ods` files and quick commands to try the tool.

## 1) Quick start (SQLite)

```bash
# from repo root
./ods2sql.py examples/people.ods | sqlite3 examples/people.sqlite

# verify
sqlite3 examples/people.sqlite "SELECT COUNT(*) FROM people;"
sqlite3 examples/people.sqlite ".schema people"
```

> Tip: For faster loads on large sheets, add `--transaction`:
>
> `./ods2sql.py --transaction examples/people.ods | sqlite3 examples/people.sqlite`

## 2) What an instrumented sheet looks like

Column **A** holds control keywords; data starts at **B**.

```
A           B          C           D          E
------------------------------------------------------------
sqltable    people
columns     id         name        is_active  joined_at
types       INT        TEXT        BOOLEAN    TEXT
            1          Alice       TRUE       2025-09-10
            2          Bob         FALSE      2025-09-11
comment     anything in this row is ignored
```

- Control keywords are case-insensitive (except comment, which must match exactly).
- Blank type cells default to TEXT.

## 3) Other useful runs

### Run scripts

Convenience scripts are provided for common targets:

- SQLite: `examples/run-sqlite.sh` (creates `people.sqlite`) 
- DuckDB: `examples/run-duckdb.sh [ODS] [DB]` (defaults to `people.ods` → `people.duckdb`)
- Postgres: `examples/run-postgres.sh [ODS]` (uses env: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)
- MySQL: `examples/run-mysql.sh [ODS]` (uses env: MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PWD, MYSQL_OPTS)

Each script is defensive (`set -euo pipefail`), checks for client binaries, and guides you if connection credentials are missing.

### Schema only / data only

```bash
./ods2sql.py --schema-only examples/people.ods | sqlite3 examples/people.sqlite
./ods2sql.py --data-only   examples/people.ods | sqlite3 examples/people.sqlite
```

### Indexes and primary key

```bash
./ods2sql.py --primary-key id examples/people.ods | sqlite3 examples/people.sqlite
sqlite3 examples/people.sqlite "SELECT name FROM sqlite_master WHERE type='index' ORDER BY 1"
```

### List detected tables (prints to stderr)

```bash
./ods2sql.py --list examples/people.ods 2> /dev/stdout
```

### Postgres/MySQL emission (string-level demo)

```bash
./ods2sql.py --dialect postgresql examples/people.ods > /tmp/people.pg.sql
./ods2sql.py --dialect mysql      examples/people.ods > /tmp/people.mysql.sql
```

These scripts are valid SQL for those engines. To actually load, run them against your DB of choice.

DuckDB tip: DuckDB accepts the Postgres-style identifiers and booleans; `run-duckdb.sh` uses `--dialect postgres` and `--transaction` for best performance.

## 4) Advanced example (optional)

`advanced.ods` demonstrates:
- Text above control rows (scanner still finds the first sqltable)
- number-columns-repeated and number-rows-repeated
- Covered (merged) cells treated as NULL
- Mixed types: floats, booleans, dates, times

Run it like the basic example and inspect the result:

```bash
./ods2sql.py --transaction examples/advanced.ods | sqlite3 examples/advanced.sqlite
sqlite3 examples/advanced.sqlite ".schema"
```

## 5) Known notes

- Empty strings are emitted as `NULL`.
- MySQL skips indexes on `TEXT/BLOB` columns (it would require prefix lengths); a warning is printed.
- Identifiers are quoted appropriately per dialect; very long index names are truncated with a short hash to stay within limits.
- If you need to avoid indexes altogether, add `--no-indices`. To index a subset, use `--index-columns "c1,c2"`, or define composite indexes with repeated `--index "c1+c2"` flags.

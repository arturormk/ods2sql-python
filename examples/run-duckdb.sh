#!/usr/bin/env bash
# Load examples/people.ods into DuckDB using ods2sql.py.
# Usage:
#   ./examples/run-duckdb.sh                        # defaults to people.ods → people.duckdb
#   ./examples/run-duckdb.sh /path/to/file.ods      # custom ODS, default DB path
#   ./examples/run-duckdb.sh /path/to/file.ods /tmp/out.duckdb  # custom DB path

set -euo pipefail

# --- Paths ---
here="$(cd "$(dirname "$0")" && pwd)"
repo="$here/.."

ods="${1:-$here/people.ods}"
db="${2:-$here/people.duckdb}"

# --- Checks ---
command -v duckdb >/dev/null 2>&1 || { echo "ERROR: 'duckdb' CLI not found. Install DuckDB (e.g., 'sudo apt install duckdb' or download from duckdb.org)."; exit 1; }
[[ -f "$repo/src/ods2sql.py" ]] || { echo "ERROR: ods2sql.py not found at $repo/src/ods2sql.py"; exit 1; }
[[ -f "$ods" ]] || { echo "ERROR: ODS file not found at $ods"; exit 1; }

echo "Loading $ods into DuckDB database $db ..."
# DuckDB is happy with standard SQL: double-quoted identifiers, TRUE/FALSE booleans.
# Use the 'postgres' dialect for emission, plus --transaction for speed.
# -batch tells the DuckDB CLI to run non-interactively and stop on error.
"$repo/src/ods2sql.py" --dialect postgres --if-not-exists --transaction "$ods" | \
  duckdb "$db" -batch

echo "Listing tables:"
duckdb "$db" -c "SHOW TABLES;" || true

echo "If a 'people' table exists, show row count:"
duckdb "$db" -c "SELECT COUNT(*) AS rows FROM people;" || true

echo "Done. Database located at: $db"

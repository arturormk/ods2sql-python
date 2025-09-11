#!/usr/bin/env bash
# Load examples/people.ods into PostgreSQL using ods2sql.py.
# Usage:
#   ./examples/run-postgres.sh                      # uses defaults below
#   PGDATABASE=mydb PGUSER=me ./examples/run-postgres.sh
#   PGHOST=db.local PGPORT=5432 ./examples/run-postgres.sh /path/to/file.ods

set -euo pipefail

# --- Config (override via environment variables) ---
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-ods2sql_examples}"
PGUSER="${PGUSER:-postgres}"
# Extra flags for psql. -X = ignore .psqlrc; ON_ERROR_STOP stops on the first error.
PSQL_FLAGS="${PSQL_FLAGS:--X -v ON_ERROR_STOP=1}"

# --- Paths ---
here="$(cd "$(dirname "$0")" && pwd)"
repo="$here/.."
ods="${1:-$here/people.ods}"   # allow optional path argument; default to examples/people.ods

# --- Checks ---
command -v psql >/dev/null 2>&1 || { echo "ERROR: 'psql' client not found. Install postgresql-client."; exit 1; }
[[ -f "$repo/src/ods2sql.py" ]] || { echo "ERROR: ods2sql.py not found at $repo/src/ods2sql.py"; exit 1; }
[[ -f "$ods" ]] || { echo "ERROR: ODS file not found at $ods"; exit 1; }

# If no password is set, try a no-password ping; if that fails, prompt securely.
if ! PGPASSWORD="${PGPASSWORD:-}" psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
  if [[ -z "${PGPASSWORD:-}" ]]; then
    read -s -p "PostgreSQL password for $PGUSER@$PGHOST:$PGPORT: " PGPASSWORD
    echo
    export PGPASSWORD
  fi
  # Try again with the provided password
  psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "SELECT 1;" >/dev/null
fi

# Create the database if it doesn't exist (connect via the 'postgres' db)
dbq=$(printf "%s" "$PGDATABASE" | sed "s/'/''/g")
exists=$(psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$dbq';" || true)
if [[ "$exists" != "1" ]]; then
  echo "Creating database: $PGDATABASE"
  psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "CREATE DATABASE \"$PGDATABASE\";"
fi

echo "Loading $ods into PostgreSQL database $PGDATABASE ..."
# Use Postgres dialect and wrap in a single transaction for speed; IF NOT EXISTS makes reruns friendlier.
"$repo/src/ods2sql.py" --dialect postgresql --if-not-exists --transaction "$ods" | \
  psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -q

echo "Listing tables:"
psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "\dt" || true

echo "If a 'people' table exists, show row count:"
psql $PSQL_FLAGS -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "SELECT COUNT(*) AS rows FROM people;" || true

echo "Done."

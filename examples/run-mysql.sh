#!/usr/bin/env bash
# Load examples/people.ods into MySQL using ods2sql.py (MySQL dialect).
# Usage:
#   ./examples/run-mysql.sh                 # uses defaults below
#   MYSQL_DB=mydb MYSQL_USER=me ./examples/run-mysql.sh
#   MYSQL_OPTS="--ssl-mode=DISABLED" ./examples/run-mysql.sh

set -euo pipefail

# --- Config (override via environment variables) ---
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DB="${MYSQL_DB:-ods2sql_examples}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_OPTS="${MYSQL_OPTS:-}"   # e.g. --ssl-mode=DISABLED or --protocol=TCP

# --- Paths ---
here="$(cd "$(dirname "$0")" && pwd)"
repo="$here/.."
ods="${1:-$here/people.ods}"   # allow optional path argument; default to examples/people.ods

# --- Checks ---
command -v mysql >/dev/null 2>&1 || { echo "ERROR: 'mysql' client not found. Install mysql-client."; exit 1; }
[[ -f "$repo/src/ods2sql.py" ]] || { echo "ERROR: ods2sql.py not found at $repo/src/ods2sql.py"; exit 1; }
[[ -f "$ods" ]] || { echo "ERROR: ODS file not found at $ods"; exit 1; }

# If no password is set, try a no-password ping first; if that fails, prompt.
if ! mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" $MYSQL_OPTS -e "SELECT 1" >/dev/null 2>&1; then
  if [[ -z "${MYSQL_PWD:-}" ]]; then
    read -s -p "MySQL password for $MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT: " MYSQL_PWD
    echo
    export MYSQL_PWD
  fi
fi

echo "Creating database (if needed): $MYSQL_DB"
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" $MYSQL_OPTS \
  -e "CREATE DATABASE IF NOT EXISTS \`$MYSQL_DB\`;"

echo "Loading $ods into MySQL database $MYSQL_DB ..."
# --if-not-exists keeps reruns idempotent-ish; MySQL ignores our --transaction flag by design.
"$repo/src/ods2sql.py" --dialect mysql --if-not-exists "$ods" | \
  mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" $MYSQL_OPTS "$MYSQL_DB"

echo "Verifying row count in 'people' (if that table exists):"
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" $MYSQL_OPTS "$MYSQL_DB" \
  -e "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE();"
mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" $MYSQL_OPTS "$MYSQL_DB" \
  -e "SELECT COUNT(*) AS rows FROM people;" || true

echo "Done."

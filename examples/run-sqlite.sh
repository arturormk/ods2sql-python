#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
db="$here/people.sqlite"
rm -f "$db"
"${here}/../src/ods2sql.py" --transaction "$here/people.ods" | sqlite3 "$db"
sqlite3 "$db" "SELECT COUNT(*) FROM people;"
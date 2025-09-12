#!/usr/bin/env bash
# Fail if there is a print( call in src/ods2sql.py that lacks a file= parameter.
set -euo pipefail
FILE=src/ods2sql.py
if grep -n "print(" "$FILE" | grep -v 'file=' >/dev/null; then
  echo "Found raw print() without file= parameter in $FILE. Use file=stderr or file=out." >&2
  exit 1
fi
exit 0

#!/usr/bin/env bash
set -euo pipefail
# Minimal fast test subset for pre-push hook.
pytest -q tests/test_parser_edges.py::test_aliases tests/test_dialects.py::test_index_name_truncation

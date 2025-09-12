#!/usr/bin/env bash
set -euo pipefail
# Minimal fast test subset for pre-push hook.
# Use existing test names to provide quick signal.
pytest -q \
	tests/test_parser_edges.py::test_aliases_columns_and_types \
	tests/test_dialects.py::test_identifier_length_truncation

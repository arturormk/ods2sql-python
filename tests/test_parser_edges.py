import re
import sys
from pathlib import Path
import subprocess

from .helpers import write_ods

SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'ods2sql.py'


def run_cli(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def test_scanning_finds_later_sqltable_or_skips(tmp_path):
    # B1: if A1 is noise, implementation either skips or finds later sqltable; current behavior finds it
    ods = tmp_path / 'b1.ods'
    rows = [
        ['', 'noise'],
        ['sqltable', 't'],
        ['columns', 'id'],
        ['types', 'INTEGER'],
        ['', 1],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    assert 'CREATE TABLE' in out


def test_aliases_columns_and_types(tmp_path):
    # B2: accept synonyms for columns/types
    ods = tmp_path / 'b2.ods'
    rows = [
        ['sqltable', 't'],
        ['fields', 'id', 'n'],
        ['type', 'INTEGER', 'TEXT'],
        ['', 1, 'x'],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    assert 'CREATE TABLE' in out and 'INSERT INTO' in out


def test_duplicate_column_names_fail_fast(tmp_path):
    # B3: duplicate column names should fail fast
    ods = tmp_path / 'b3.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'id', 'ID'],  # duplicate case-insensitive
        ['types', 'INTEGER', 'INTEGER'],
        ['', 1, 2],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 2 or 'duplicate column names' in err.lower()


def test_repetition_expand_and_skip_empty(tmp_path):
    # B4/B6: number-columns/rows repeated; empty strings should be NULLs and fully empty rows skipped
    ods = tmp_path / 'b4.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'a', 'b', 'c'],
        ['types', 'TEXT', 'TEXT', 'TEXT'],
        # A data row with cols_repeat expanding; include an empty string
        ['', {'value': 'x', 'vtype': 'string', 'cols_repeat': 2}, ''],
        # Repeated empty row should be collapsed/skipped
        [
            {'value': None, 'vtype': 'string'},
            {'value': None, 'vtype': 'string'},
            {'value': None, 'vtype': 'string'},
        ],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    # Expect one INSERT row with NULL for empty string
    assert 'INSERT INTO' in out
    # Ensure emitted INSERT has two 'x' and a NULL
    assert "VALUES ('x', 'x', NULL)" in out


def test_covered_cells_are_null(tmp_path):
    # B5: covered cells -> NULL
    ods = tmp_path / 'b5.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'a', 'b'],
        ['types', 'TEXT', 'TEXT'],
        ['', {'value': 'x', 'vtype': 'string'}, {'covered': True}],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    # Second value should be NULL
    assert re.search(r"VALUES \('x', NULL\)", out)


def test_comment_rows_ignored(tmp_path):
    # B7: first-cell 'comment' row ignored
    ods = tmp_path / 'b7.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'a'],
        ['types', 'INTEGER'],
        ['comment', 'ignored'],
        ['', 1],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    assert 'ignored' not in out


def test_text_column_uses_percentage_display(tmp_path):
    # B8: When col_type is TEXT and cell type is percentage, emit formatted value like '12%'
    ods = tmp_path / 'b8.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'p'],
        ['types', 'TEXT'],
        ['', {'value': 0.12, 'vtype': 'percentage'}],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    # Expect INSERT with '12%'
    assert 'INSERT INTO' in out
    assert "'12%'" in out

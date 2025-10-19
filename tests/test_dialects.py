import re
import sys
from pathlib import Path
import subprocess

from .helpers import write_ods

SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'ods2sql.py'


def run_cli(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def test_quoting_and_booleans(tmp_path):
    ods = tmp_path / 'c1.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'yes'],
        ['types', 'BOOLEAN'],
        ['', {'value': True, 'vtype': 'boolean'}],
        ['', {'value': False, 'vtype': 'boolean'}],
    ]
    write_ods(ods, 'S', rows)
    for dialect, true_lit, false_lit, q in (
        ('sqlite', '1', '0', '"'),
        ('postgres', 'TRUE', 'FALSE', '"'),
        ('mysql', 'TRUE', 'FALSE', '`'),
    ):
        rc, out, err = run_cli(['--dialect', dialect, str(ods)])
        assert rc == 0
        assert 'CREATE TABLE' in out
        # Quoted identifier
        assert f'{q}t{q}' in out
        assert true_lit in out and false_lit in out


def test_identifier_length_truncation(tmp_path):
    ods = tmp_path / 'c3.ods'
    long_table = 't_' + ('a' * 80)
    rows = [
        ['sqltable', long_table],
        ['columns', 'a'],
        ['types', 'INTEGER'],
        ['', 1],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli(['--dialect', 'postgres', str(ods)])
    assert rc == 0
    # index name should be shortened with hash; presence of idx_ prefix implies generation
    assert re.search(r'CREATE INDEX .*\"idx_', out)


def test_mysql_text_blob_index_skipped(tmp_path):
    ods = tmp_path / 'c4.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'a'],
        ['types', 'TEXT'],
        ['', 'x'],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli(['--dialect', 'mysql', str(ods)])
    assert rc == 0
    # No CREATE INDEX for column 'a'
    assert 'CREATE INDEX' not in out
    assert 'skipping MySQL index on TEXT/BLOB' in err

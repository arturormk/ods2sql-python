import re
import sqlite3
import sys
from pathlib import Path
import subprocess

from .helpers import write_ods
from typing import Optional


SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'ods2sql.py'


def run_cli(args: list[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_roundtrip_sqlite(tmp_path):
    # A1: happy path, one table with types and 5 rows
    ods = tmp_path / 'a1.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'id', 'name'],
        ['types', 'INTEGER', 'TEXT'],
        ['', 1, 'a'],
        ['', 2, 'b'],
        ['', 3, 'c'],
        ['', 4, 'd'],
        ['', 5, 'e'],
    ]
    write_ods(ods, 'Sheet1', rows)
    rc, out, err = run_cli([str(ods)])
    assert rc == 0
    assert 'CREATE TABLE' in out
    # Execute in sqlite
    con = sqlite3.connect(':memory:')
    con.executescript(out)
    cur = con.execute('select count(*) from t')
    assert cur.fetchone()[0] == 5


def test_schema_then_data_split(tmp_path):
    # A2: --schema-only followed by --data-only
    ods = tmp_path / 'a2.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'id', 'name'],
        ['types', 'INTEGER', 'TEXT'],
        ['', 1, 'a'],
        ['', 2, 'b'],
    ]
    write_ods(ods, 'Sheet1', rows)
    rc1, out_schema, err1 = run_cli(['--schema-only', str(ods)])
    rc2, out_data, err2 = run_cli(['--data-only', str(ods)])
    assert rc1 == 0 and rc2 == 0
    assert 'CREATE TABLE' in out_schema and 'INSERT INTO' not in out_schema
    assert 'INSERT INTO' in out_data and 'CREATE TABLE' not in out_data
    con = sqlite3.connect(':memory:')
    con.executescript(out_schema)
    con.executescript(out_data)
    assert con.execute('select count(*) from t').fetchone()[0] == 2


def test_batching_groups_values(tmp_path):
    # A3: batching only (no --transaction flag in current CLI)
    ods = tmp_path / 'a3.ods'
    rows = [
        ['sqltable', 't'],
        ['columns', 'id'],
        ['types', 'INTEGER'],
        ['', 1],
        ['', 2],
        ['', 3],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli(['--batch', '2', str(ods)])
    assert rc == 0
    # Expect at least one grouped VALUES clause
    assert re.search(r'INSERT INTO .* VALUES \([^)]*\), \([^)]*\);', out)
    # Script still loads
    con = sqlite3.connect(':memory:')
    con.executescript(out)
    assert con.execute('select count(*) from t').fetchone()[0] == 3


def test_primary_key_and_indexes(tmp_path):
    # A4: --primary-key id; per-column indexes exist for non-PK
    ods = tmp_path / 'a4.ods'
    rows = [
        ['sqltable', 'users'],
        ['columns', 'id', 'name'],
        ['types', 'INTEGER', 'TEXT'],
        ['', 1, 'x'],
    ]
    write_ods(ods, 'Sheet1', rows)
    rc, out, err = run_cli(['--primary-key', 'id', str(ods)])
    assert rc == 0
    assert 'PRIMARY KEY' in out
    con = sqlite3.connect(':memory:')
    con.executescript(out)
    # ensure index exists for non-PK column only
    idx_rows = con.execute(
        "select name from sqlite_master where type='index' and tbl_name='users'"
    ).fetchall()
    idx_names = {r[0] for r in idx_rows}
    # There should be at least one index on 'name'
    assert any('name' in n for n in idx_names)
    # No index solely on 'id' (PK)
    assert not any(n.endswith('_id') for n in idx_names)


def test_table_filter_only_selected_emitted(tmp_path):
    # A5: multiple tables; --table filters
    ods = tmp_path / 'a5.ods'
    rows = [
        ['sqltable', 't1'],
        ['columns', 'id'],
        ['types', 'INTEGER'],
        ['', 1],
        ['sqltable', 't2'],
        ['columns', 'id'],
        ['types', 'INTEGER'],
        ['', 2],
    ]
    write_ods(ods, 'S', rows)
    rc, out, err = run_cli(['--table', 't2', str(ods)])
    assert rc == 0
    assert 'CREATE TABLE' in out
    assert 't2' in out and 't1' not in out

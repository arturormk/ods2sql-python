import sys
from pathlib import Path
import subprocess

from .helpers import write_ods

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "ods2sql.py"


def run_cli(args):
	p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
	return p.returncode, p.stdout, p.stderr


def test_exit_codes_and_warnings(tmp_path):
	# D1: bad file -> 2
	rc, out, err = run_cli([str(tmp_path / "nope.ods")])
	assert rc == 2
	assert "ERROR" in err

	# D1: no instrumented tables -> 0 with [WARN]
	ods = tmp_path / "d1.ods"
	write_ods(ods, "S", [["", "no tables here"]])
	rc, out, err = run_cli([str(ods)])
	assert rc == 0
	assert "[WARN]" in err and out.strip() == ""


def test_streams_stdout_sql_stderr_diag(tmp_path):
	# D2: SQL only on stdout; diagnostics on stderr
	ods = tmp_path / "d2.ods"
	rows = [["sqltable", "t"], ["columns", "a"], ["types", "INTEGER"], ["", 1]]
	write_ods(ods, "S", rows)
	rc, out, err = run_cli([str(ods)])
	assert rc == 0
	assert "CREATE TABLE" in out
	# stderr may be empty on clean runs, but should not contain SQL
	assert "CREATE TABLE" not in err


def test_dialect_alias_postgresql_is_accepted(tmp_path):
	# D3: --dialect postgresql accepted (alias)
	ods = tmp_path / "d3.ods"
	rows = [["sqltable", "t"], ["columns", "a"], ["types", "INTEGER"], ["", 1]]
	write_ods(ods, "S", rows)
	p = subprocess.run([sys.executable, str(SCRIPT), "--dialect", "postgresql", str(ods)], capture_output=True, text=True)
	assert p.returncode == 0
	assert "CREATE TABLE" in p.stdout


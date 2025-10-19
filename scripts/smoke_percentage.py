import sys
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

# Reuse the test helper to generate a tiny ODS
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from helpers import write_ods  # type: ignore

SCRIPT = Path(__file__).resolve().parents[1] / 'src' / 'ods2sql.py'


def main() -> None:
    with TemporaryDirectory() as td:
        p = Path(td)
        ods = p / 'pct.ods'
        rows = [
            ['sqltable', 't'],
            ['columns', 'p'],
            ['types', 'TEXT'],
            ['', {'value': 0.375, 'vtype': 'percentage'}],
        ]
        write_ods(ods, 'S', rows)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(ods)], capture_output=True, text=True
        )
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            sys.exit(proc.returncode)
        # Simple assert in script mode
        if "'37.5%'" not in proc.stdout:
            print('Did not find expected formatted percentage in output', file=sys.stderr)
            sys.exit(1)
        print('OK: formatted percentage found', file=sys.stderr)


if __name__ == '__main__':
    main()

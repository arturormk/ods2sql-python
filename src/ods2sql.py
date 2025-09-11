#!/usr/bin/env python3
"""
ods2sql.py — extract SQL from instrumented LibreOffice Calc .ods files

USAGE
    $ ./ods2sql.py file.ods | sqlite3 out.sqlite

INSTRUMENTATION (per sheet/tab)
    - Put your data in columns. Column A is reserved for control keywords; data starts at column B.
    - The sheet may contain text above; scanning starts at the first control row:
            Control row:  A = 'sqltable', B = <table_name>
            Aliases/synonyms are accepted for later control rows:
                Next:      A = 'sqlcolumn' or 'columns' or 'column' or 'fields' ; non-empty cells in B.. define column names
                Next:      A = 'sqltype' or 'types' or 'type' ; non-empty cells in B.. define SQL types (blank -> TEXT)
        Any row whose first cell is **exactly** 'comment' is ignored.
    - Data rows have an empty first cell in column A. Fully empty data rows are skipped.
    - Multiple tables per sheet are supported; each new 'sqltable' row starts a new block.

FEATURES
    - Pure standard library: zipfile + xml.etree to parse .ods (OpenDocument) — no dependencies.
    - Multiple tables across multiple sheets.
    - Dialects: sqlite (default), postgres/postgresql, mysql (affects identifier quoting & booleans).
    - Performance: collapses repeated empty rows, batches INSERTs (configurable), optional single-transaction output.
    - Indexing & keys:
            * By default, creates a non-unique index for every column (sqlite-friendly browsing).
            * --no-indices disables index creation.
            * --index-columns "c1,c2" indexes only those columns (instead of all).
            * --index "c1+c2" defines a composite index (flag may repeat).
            * --primary-key "c1[,c2,...]" sets a PRIMARY KEY; PK columns are not indexed redundantly.

OPTIONS (selection)
    --dialect {sqlite,postgres,postgresql,mysql}  SQL dialect for quoting & booleans (default: sqlite)
    --if-not-exists                              Use IF NOT EXISTS in CREATE TABLE/INDEX when supported
    --no-drop                                    Do not emit DROP TABLE IF EXISTS
    --schema-only / --data-only                  Emit only DDL or only INSERTs
    --batch N                                    Rows per INSERT statement (0/1 for one row per INSERT)
    --table NAME                                 Only export the named table (may repeat)
    --list                                       List detected tables & columns to stderr and exit
    --transaction                                Wrap the emitted SQL in a single transaction (SQLite/Postgres)
    --no-indices                                 Do not emit CREATE INDEX statements
    --index-columns "c1,c2"                      Per-column indexes (defaults to all columns)
    --index "c1+c2"                               Composite index (may repeat)
    --primary-key "c1[,c2,...]"                 PRIMARY KEY columns for CREATE TABLE
    --version                                    Show program version and exit

This program emits only SQL on stdout. Diagnostic messages go to stderr.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from collections import Counter
from decimal import Decimal
from typing import Optional, Iterable

__version__ = "0.1.0"

# Namespaces used in ODF/ODS content.xml
NS = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'table':  'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'text':   'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
}

# Control keyword literals (customize if you want different markers)
CONTROL_SQLTABLE = 'sqltable'  # 'table' might be found in some spreadsheets
CONTROL_SQLCOLUMN = 'sqlcolumn'
CONTROL_SQLTYPE = 'sqltype'
CONTROL_COMMENT = 'comment'

# Accept common synonyms (forgiving) — except comments which must be exactly 'comment'
KW_SQLTABLE = {CONTROL_SQLTABLE, 'sqltable'}
KW_SQLCOLUMN = {CONTROL_SQLCOLUMN, 'sqlcolumn', 'columns', 'column', 'fields'}
KW_SQLTYPE = {CONTROL_SQLTYPE, 'sqltype', 'types', 'type'}
KW_COMMENT = {CONTROL_COMMENT}  # only 'comment' hides a row

@dataclass
class TableSpec:
    sheet: str
    name: str
    columns: list[tuple[str, str]]  # list of (name, sqltype)
    rows: list[list[object]]        # data rows with python values

class ODSParseError(RuntimeError):
    pass

# ------------------------
# ODS READER (pure stdlib)
# ------------------------

def _iter_tables(content_xml: bytes) -> Iterable[tuple[str, ET.Element]]:
    root = ET.fromstring(content_xml)
    for table in root.findall('.//table:table', NS):
        sheet_name = table.get(f"{{{NS['table']}}}name") or 'Sheet'
        yield sheet_name, table

def _cell_text(cell: ET.Element) -> str:
    # Join all text:p blocks; preserve line breaks if multiple <text:p>
    parts = []
    for p in cell.findall('text:p', NS):
        parts.append(''.join(p.itertext()))
    return '\n'.join(parts).strip()

def _cell_value(cell: ET.Element):
    """Return a Python value for a table:table-cell element."""
    # covered cells (part of a merge) behave like empty
    if cell.tag.endswith('covered-table-cell'):
        return None

    vtype = cell.get(f"{{{NS['office']}}}value-type")
    if vtype == 'string' or vtype is None:
        s = _cell_text(cell)
        return s if s != '' else None
    if vtype in ('float', 'currency', 'percentage'):
        v = cell.get(f"{{{NS['office']}}}value")
        if v is None:
            s = _cell_text(cell)
            return Decimal(s) if s else None
        try:
            return Decimal(v)
        except Exception:
            return Decimal(str(v))
    if vtype == 'boolean':
        b = cell.get(f"{{{NS['office']}}}boolean-value")
        return True if (b or '').lower() == 'true' else False
    if vtype == 'date':  # office:date-value in ISO 8601
        return cell.get(f"{{{NS['office']}}}date-value")
    if vtype == 'time':  # office:time-value in PTxxHxxMxxS
        return cell.get(f"{{{NS['office']}}}time-value")
    # fallback to string
    s = _cell_text(cell)
    return s if s != '' else None

def _expand_row(row: ET.Element) -> list[list[object]]:
    cells: list[object] = []
    for el in row:
        tag = el.tag.split('}')[-1]
        if tag == 'table-cell':
            repeat = int(el.get(f"{{{NS['table']}}}number-columns-repeated", '1'))
            val = _cell_value(el)
            cells.extend([val] * repeat)
        elif tag == 'covered-table-cell':
            repeat = int(el.get(f"{{{NS['table']}}}number-columns-repeated", '1'))
            cells.extend([None] * repeat)
        # ignore other nodes
    # Row repetition
    rows_rep = int(row.get(f"{{{NS['table']}}}number-rows-repeated", '1'))
    if rows_rep == 1:
        return [cells]
    # If the row is entirely empty, don't materialize millions of repeats—return a single empty row.
    if all(c is None for c in cells):
        return [cells]
    return [cells[:] for _ in range(rows_rep)]

# ------------------------
# EXTRACTION LOGIC
# ------------------------

def _is_keyword(val: Optional[object], names) -> bool:
    """Return True if val (string) matches any name (case/space-insensitive).
    `names` can be a string or an iterable of strings.
    """
    if not isinstance(val, str):
        return False
    v = val.strip().lower()
    if isinstance(names, str):
        return v == names.strip().lower()
    try:
        norm = {n.strip().lower() for n in names if isinstance(n, str) and n.strip()}
    except TypeError:
        return False
    return v in norm

def extract_tables_from_sheet(sheet_name: str, table_el: ET.Element, stderr) -> list[TableSpec]:
    """Scan a single sheet for instrumented blocks and build TableSpec objects."""
    tables: list[TableSpec] = []

    current_name: Optional[str] = None
    col_indices: list[int] = []  # indexes in the row (excluding control col) to keep
    col_defs: list[tuple[str, str]] = []
    data_rows: list[list[object]] = []

    def flush():
        nonlocal current_name, col_indices, col_defs, data_rows
        if current_name and col_defs:
            tables.append(TableSpec(sheet=sheet_name, name=current_name, columns=col_defs[:], rows=data_rows[:]))
        current_name, col_indices, col_defs, data_rows = None, [], [], []

    for row_el in table_el.findall('table:table-row', NS):
        for row in _expand_row(row_el):
            first = row[0] if row else None
            if _is_keyword(first, KW_COMMENT):
                continue
            if _is_keyword(first, KW_SQLTABLE):
                # starting a new block; flush previous if any
                if current_name:
                    flush()
                else:
                    # reset any lingering state from a discarded block
                    col_indices, col_defs, data_rows = [], [], []
                current_name = str(row[1] or '').strip()
                if not current_name:
                    print(f"[WARN] Sheet '{sheet_name}': {CONTROL_SQLTABLE} row missing table name; block ignored.", file=stderr)
                    current_name = None
                continue
            if current_name is None:
                # ignore rows until a CONTROL_SQLTABLE marker is found
                continue
            if _is_keyword(first, KW_SQLCOLUMN):
                headers = [(str(c).strip() if c is not None else '') for c in row[1:]]
                col_indices = [i for i, h in enumerate(headers) if h != '']
                if not col_indices:
                    print(f"[WARN] Sheet '{sheet_name}', table '{current_name}': empty columns row; block ignored.", file=stderr)
                    # discard current block state entirely
                    current_name = None
                    col_indices, col_defs, data_rows = [], [], []
                    continue
                # Fail fast on duplicate column names (case-insensitive)
                selected = [headers[i] for i in col_indices]
                counts = Counter(h.lower() for h in selected)
                dups = [h for h, c in counts.items() if c > 1]
                if dups:
                    raise ODSParseError(
                        f"Sheet '{sheet_name}', table '{current_name}': duplicate column names: {', '.join(sorted(dups))}"
                    )
                # Provisional column defs with TEXT, to be updated by sqltype
                col_defs = [(headers[i], 'TEXT') for i in col_indices]
                continue
            if _is_keyword(first, KW_SQLTYPE):
                if not col_defs:
                    print(f"[WARN] Sheet '{sheet_name}', table '{current_name}': {CONTROL_SQLTYPE} before columns row; using TEXT.", file=stderr)
                types = [(str(c).strip() if c is not None else '') for c in row[1:]]
                for idx, (name, _) in enumerate(col_defs):
                    t = types[col_indices[idx]] if col_indices[idx] < len(types) else ''
                    col_defs[idx] = (name, t or 'TEXT')
                continue
            # Data row: first cell empty
            if (first is None) or (isinstance(first, str) and first.strip() == ''):
                if not col_defs:
                    # data before columns row
                    continue
                values = []
                # pick selected indices, offset by +1 because col 0 is the control column
                for i in col_indices:
                    j = 1 + i
                    v = row[j] if j < len(row) else None
                    values.append(v)
                # Skip fully empty data rows
                if all(v is None or (isinstance(v, str) and v.strip() == '') for v in values):
                    continue
                data_rows.append(values)
                continue
            # Any other keyword starts a new block implicitly
            if isinstance(first, str) and first.strip() != '':
                flush()
                current_name = None
                # then re-process this row in case it's another CONTROL_SQLTABLE
                if _is_keyword(first, KW_SQLTABLE):
                    current_name = str(row[1] or '').strip()
                else:
                    # ignore until next sqltable
                    pass
    # flush last
    flush()
    return tables

# ------------------------
# SQL EMISSION
# ------------------------

class Dialect:
    def __init__(self, name: str):
        name = name.lower()
        if name == 'postgresql':
            name = 'postgres'
        if name not in ('sqlite', 'postgres', 'mysql'):
            raise ValueError('Unsupported dialect: ' + name)
        self.name = name
        self.qchar = '"' if name in ('sqlite', 'postgres') else '`'

    def qid(self, ident: str) -> str:
        q = self.qchar
        # allow dots so users can do schema.table in PG/MySQL; quote parts separately
        parts = [p for p in ident.split('.') if p]
        def _q(p: str) -> str:
            return q + p.replace(q, q + q) + q
        return '.'.join(_q(p) for p in parts) if parts else _q(ident)

    def lit(self, v) -> str:
        if v is None:
            return 'NULL'
        # Unconditionally treat empty strings as SQL NULL
        if isinstance(v, str) and v == '':
            return 'NULL'
        if isinstance(v, bool):
            if self.name == 'sqlite':
                return '1' if v else '0'
            return 'TRUE' if v else 'FALSE'
        if isinstance(v, (int,)):
            return str(v)
        if isinstance(v, Decimal):
            return format(v, 'f')
        if isinstance(v, float):
            # avoid scientific notation
            return ('%.15g' % v)
        # Everything else as string
        s = str(v)
        return "'" + s.replace("'", "''") + "'"

    def create_table(self, name: str, cols: list[tuple[str, str]], if_not_exists: bool, primary_key: Optional[list[str]] = None) -> str:
        ine = ' IF NOT EXISTS' if if_not_exists else ''
        colsql = ', '.join(f"{self.qid(cn)} {ct}" for cn, ct in cols)
        pk = ''
        if primary_key:
            pkcols = ', '.join(self.qid(c) for c in primary_key)
            pk = f", PRIMARY KEY ({pkcols})"
        return f"CREATE TABLE{ine} {self.qid(name)} ({colsql}{pk});"

    def drop_table(self, name: str) -> str:
        return f"DROP TABLE IF EXISTS {self.qid(name)};"

    def insert_many(self, name: str, cols: list[str], rows: list[list[object]]) -> str:
        csql = ', '.join(self.qid(c) for c in cols)
        values_sql = ', '.join('(' + ', '.join(self.lit(v) for v in r) + ')' for r in rows)
        return f"INSERT INTO {self.qid(name)} ({csql}) VALUES {values_sql};"

    def create_index(self, index_name: str, table: str, columns: list[str], if_not_exists: bool) -> str:
        # IF NOT EXISTS is supported by sqlite & postgres, not by mysql
        ine = ''
        if if_not_exists and self.name in ('sqlite', 'postgres'):
            ine = ' IF NOT EXISTS'
        cols_sql = ', '.join(self.qid(c) for c in columns)
        return f"CREATE INDEX{ine} {self.qid(index_name)} ON {self.qid(table)} ({cols_sql});"

def _slug(s: str) -> str:
    """Make a safe identifier fragment: lowercase, non-alnum -> '_', collapse repeats."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s or 'x'

def _limit_identifier(name: str, dialect_name: str) -> str:
    """Limit identifier length for specific dialects; add a short hash if truncated.
    Postgres: 63 bytes; MySQL: 64; SQLite: practically unlimited (use 64 for portability).
    """
    max_len = 64
    if dialect_name == 'postgres':
        max_len = 63
    elif dialect_name == 'mysql':
        max_len = 64
    else:  # sqlite or others
        max_len = 64
    if len(name) <= max_len:
        return name
    suffix = '_' + hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]
    head = name[: max_len - len(suffix)]
    return head + suffix

# ------------------------
# CLI / MAIN
# ------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Extract SQL from instrumented .ods spreadsheets (pure stdlib).',
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('ods', help='Path to .ods file')
    p.add_argument('--dialect', choices=['sqlite', 'postgres', 'postgresql', 'mysql'], default='sqlite', help='SQL dialect for quoting & booleans')
    p.add_argument('--if-not-exists', action='store_true', help='Use IF NOT EXISTS in CREATE TABLE/INDEX (where supported)')
    p.add_argument('--no-drop', action='store_true', help='Do not emit DROP TABLE IF EXISTS')
    p.add_argument('--schema-only', action='store_true', help='Emit only CREATE TABLE statements')
    p.add_argument('--data-only', action='store_true', help='Emit only INSERT statements')
    p.add_argument('--batch', type=int, default=500, help='Rows per INSERT statement (0/1 for one row per INSERT)')
    p.add_argument('--table', action='append', default=[], help='Only export tables with this name (may repeat)')
    p.add_argument('--list', action='store_true', help='List detected tables & columns to stderr and exit')
    p.add_argument('--transaction', action='store_true', help='Wrap output in a single transaction (SQLite/Postgres)')
    p.add_argument('--no-indices', action='store_true', help='Do not create any indices')
    p.add_argument('--index-columns', default='', help='Comma-separated list of column names to index (defaults to all columns)')
    p.add_argument('--index', action='append', default=[], help='Define an index: columns separated by + (e.g., --index "col1+col2"). May repeat.')
    p.add_argument('--primary-key', default='', help='Comma-separated column name(s) for a PRIMARY KEY (omit for none)')
    p.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity (stderr)')
    p.add_argument('--version', action='version', version=f"ods2sql.py {__version__}")
    return p.parse_args(argv)

def read_content_xml(ods_path: str) -> bytes:
    try:
        with zipfile.ZipFile(ods_path, 'r') as z:
            return z.read('content.xml')
    except KeyError:
        raise ODSParseError("content.xml not found in .ods (is this a valid LibreOffice Calc file?)")
    except FileNotFoundError:
        raise ODSParseError(f"File not found: {ods_path}")


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        content = read_content_xml(args.ods)
        dialect = Dialect(args.dialect)

        # Parse all sheets and extract tables
        tables: list[TableSpec] = []
        for sheet_name, table_el in _iter_tables(content):
            tlist = extract_tables_from_sheet(sheet_name, table_el, sys.stderr)
            if tlist:
                tables.extend(tlist)

        if not tables:
            print('[WARN] No instrumented tables found.', file=sys.stderr)
            return 0

        if args.verbose:
            for t in tables:
                print(f"[INFO] {t.sheet}:{t.name}  cols={len(t.columns)} rows={len(t.rows)}", file=sys.stderr)

        # Filter by --table if provided
        if args.table:
            wanted = set(args.table)
            tables = [t for t in tables if t.name in wanted]
            if not tables:
                print('[WARN] After filtering, no tables remained.', file=sys.stderr)
                return 0

        if args.list:
            for t in tables:
                cols = ', '.join(f"{n} {ty}" for n, ty in t.columns)
                print(f"- {t.name}  (sheet: {t.sheet}) columns: {cols} rows: {len(t.rows)}", file=sys.stderr)
            return 0

        # Emit SQL -----------------------------------
        out = sys.stdout
        if args.transaction and dialect.name in ('sqlite', 'postgres'):
            print('BEGIN;', file=out)

        for t in tables:
            col_names = [c[0] for c in t.columns]
            col_types = {n: (ty or '').strip() for n, ty in t.columns}
            # Parse primary key list
            pk_cols: list[str] = []
            if args.primary_key.strip():
                pk_cols = [c.strip() for c in args.primary_key.split(',') if c.strip()]
                # de-duplicate while preserving order
                pk_cols = list(dict.fromkeys(pk_cols))
                unknown_pk = [c for c in pk_cols if c not in col_names]
                if unknown_pk:
                    print(f"[WARN] Table '{t.name}': unknown PRIMARY KEY columns: {', '.join(unknown_pk)}", file=sys.stderr)
                    pk_cols = [c for c in pk_cols if c in col_names]
            if not args.data_only:
                if not args.no_drop:
                    print(dialect.drop_table(t.name), file=out)
                print(dialect.create_table(t.name, t.columns, args.if_not_exists, pk_cols or None), file=out)
                # Indexing
                if not args.no_indices:
                    # 1) Composite indexes via --index (may repeat)
                    seen_indexes: set[tuple[str, ...]] = set()
                    for spec in args.index:
                        cols = [c.strip() for c in spec.split('+') if c.strip()]
                        if not cols:
                            continue
                        unknown = [c for c in cols if c not in col_names]
                        if unknown:
                            print(f"[WARN] Table '{t.name}': unknown columns in index '{spec}': {', '.join(unknown)}", file=sys.stderr)
                            cols = [c for c in cols if c in col_names]
                        if not cols:
                            continue
                        # MySQL cannot index TEXT/BLOB without prefix length; skip with a warning.
                        if dialect.name == 'mysql':
                            tb_cols = [c for c in cols if 'text' in col_types.get(c, '').lower() or 'blob' in col_types.get(c, '').lower()]
                            if tb_cols:
                                print(f"[WARN] Table '{t.name}': skipping MySQL index on TEXT/BLOB columns: {', '.join(tb_cols)}", file=sys.stderr)
                                continue
                        # Skip if equal to PK columns set (ignoring order) to avoid redundancy
                        if pk_cols and set(cols) == set(pk_cols):
                            continue
                        key = tuple(cols)
                        if key in seen_indexes:
                            continue
                        seen_indexes.add(key)
                        iname = _limit_identifier(f"idx_{_slug(t.name)}_{_slug('_'.join(cols))}", dialect.name)
                        print(dialect.create_index(iname, t.name, cols, args.if_not_exists), file=out)

                    # 2) Simple per-column indexes (legacy/default behavior)
                    if args.index_columns.strip():
                        desired = [c.strip() for c in args.index_columns.split(',') if c.strip()]
                        unknown = [c for c in desired if c not in col_names]
                        if unknown:
                            print(f"[WARN] Table '{t.name}': unknown columns for indexing: {', '.join(unknown)}", file=sys.stderr)
                        idx_cols = [c for c in desired if c in col_names]
                    else:
                        idx_cols = col_names
                    # Do not create indexes for columns that are part of the PRIMARY KEY
                    if pk_cols:
                        idx_cols = [c for c in idx_cols if c not in pk_cols]
                    for c in idx_cols:
                        if dialect.name == 'mysql':
                            ty = col_types.get(c, '')
                            if 'text' in ty.lower() or 'blob' in ty.lower():
                                print(f"[WARN] Table '{t.name}': skipping MySQL index on TEXT/BLOB column: {c}", file=sys.stderr)
                                continue
                        key = (c,)
                        if key in seen_indexes:
                            continue
                        seen_indexes.add(key)
                        iname = _limit_identifier(f"idx_{_slug(t.name)}_{_slug(c)}", dialect.name)
                        print(dialect.create_index(iname, t.name, [c], args.if_not_exists), file=out)
            if not args.schema_only and t.rows:
                batch = max(1, args.batch)
                if args.batch <= 1:
                    batch = 1
                for i in range(0, len(t.rows), batch):
                    chunk = t.rows[i:i+batch]
                    print(dialect.insert_many(t.name, col_names, chunk), file=out)

        if args.transaction and dialect.name in ('sqlite', 'postgres'):
            print('COMMIT;', file=out)
        return 0

    except ODSParseError as e:
        print('[ERROR]', e, file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
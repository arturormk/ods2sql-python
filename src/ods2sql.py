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
import locale
import hashlib
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Iterable, Dict

__version__ = '0.1.1'

# Namespaces used in ODF/ODS content.xml
NS = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'number': 'urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0',
}

# Simple style maps built from content.xml to support formatting fallbacks
_STYLE_CELL_TO_DATA: Dict[str, str] = {}
_STYLE_PERCENT_DECIMALS: Dict[str, int] = {}


def _build_style_maps(content_xml: bytes) -> None:
    global _STYLE_CELL_TO_DATA, _STYLE_PERCENT_DECIMALS
    _STYLE_CELL_TO_DATA = {}
    _STYLE_PERCENT_DECIMALS = {}
    try:
        root = ET.fromstring(content_xml)
    except ET.ParseError:
        return
    # Cell styles in automatic styles and styles
    for base in ('office:automatic-styles', 'office:styles'):
        for style in root.findall(f'.//{base}/style:style', NS):
            if style.get(f"{{{NS['style']}}}family") == 'table-cell':
                name = style.get(f"{{{NS['style']}}}name")
                data_name = style.get(f"{{{NS['style']}}}data-style-name")
                if name and data_name:
                    _STYLE_CELL_TO_DATA[name] = data_name
        # Percentage data styles
        for pst in root.findall(f'.//{base}/number:percentage-style', NS):
            dname = pst.get(f"{{{NS['style']}}}name")
            dp = pst.get(f"{{{NS['number']}}}decimal-places")
            if dname and dp is not None:
                try:
                    _STYLE_PERCENT_DECIMALS[dname] = int(dp)
                except ValueError:
                    pass


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
    rows: list[list[object]]  # data rows with python values


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


@dataclass
class Cell:
    """Holds both the typed value and the display text for a cell."""

    value: object | None
    text: str
    vtype: Optional[str]
    style_name: Optional[str] = None


def _cell_parsed(cell: ET.Element) -> Cell:
    """Parse a table:table-cell element into a Cell(value, text, vtype)."""
    # covered cells (part of a merge) behave like empty
    if cell.tag.endswith('covered-table-cell'):
        return Cell(value=None, text='', vtype=None, style_name=None)

    vtype = cell.get(f"{{{NS['office']}}}value-type")
    # Always capture text (may be empty for numeric types in many ODS docs)
    text = _cell_text(cell)
    style_name = cell.get(f"{{{NS['table']}}}style-name")

    if vtype == 'string' or vtype is None:
        s = text
        return Cell(value=(s if s != '' else None), text=s, vtype='string', style_name=style_name)
    elif vtype in ('float', 'currency', 'percentage'):
        v = cell.get(f"{{{NS['office']}}}value")
        if v is None:
            s = text
            val = Decimal(s) if s else None
        else:
            try:
                val = Decimal(v)
            except Exception:
                val = Decimal(str(v))
        return Cell(value=val, text=text, vtype=vtype, style_name=style_name)
    elif vtype == 'boolean':
        b = cell.get(f"{{{NS['office']}}}boolean-value")
        val = True if (b or '').lower() == 'true' else False
        return Cell(value=val, text=text, vtype='boolean', style_name=style_name)
    elif vtype == 'date':  # office:date-value in ISO 8601
        return Cell(
            value=cell.get(f"{{{NS['office']}}}date-value"),
            text=text,
            vtype='date',
            style_name=style_name,
        )
    elif vtype == 'time':  # office:time-value in PTxxHxxMxxS
        return Cell(
            value=cell.get(f"{{{NS['office']}}}time-value"),
            text=text,
            vtype='time',
            style_name=style_name,
        )
    else:
        # fallback to string
        s = text
        return Cell(value=(s if s != '' else None), text=s, vtype=vtype, style_name=style_name)


def _expand_row(row: ET.Element) -> list[list[Cell]]:
    cells: list[Cell] = []
    for el in row:
        tag = el.tag.split('}')[-1]
        if tag == 'table-cell':
            repeat = int(el.get(f"{{{NS['table']}}}number-columns-repeated", '1'))
            parsed = _cell_parsed(el)
            cells.extend([parsed] * repeat)
        elif tag == 'covered-table-cell':
            repeat = int(el.get(f"{{{NS['table']}}}number-columns-repeated", '1'))
            cells.extend([Cell(value=None, text='', vtype=None, style_name=None)] * repeat)
        # ignore other nodes
    # Row repetition
    rows_rep = int(row.get(f"{{{NS['table']}}}number-rows-repeated", '1'))
    if rows_rep == 1:
        return [cells]
    # If the row is entirely empty, don't materialize millions of repeats—return a single empty row.
    if all(c.value is None and (c.text.strip() == '') for c in cells):
        return [cells]
    return [cells[:] for _ in range(rows_rep)]


# ------------------------
# EXTRACTION LOGIC
# ------------------------


def _is_keyword(val: Optional[object], names) -> bool:
    """Return True if val (string) matches any name (case/space-insensitive).
    `names` can be a string or an iterable of strings.
    """
    # Unwrap Cell if needed
    if isinstance(val, Cell):
        candidate = val.value if isinstance(val.value, str) else val.text
    else:
        candidate = val
    if not isinstance(candidate, str):
        return False
    v = candidate.strip().lower()
    if isinstance(names, str):
        return v == names.strip().lower()
    try:
        norm = {n.strip().lower() for n in names if isinstance(n, str) and n.strip()}
    except TypeError:
        return False
    return v in norm


def _cell_for_text_display(cell: Cell) -> Optional[str]:
    """Return a formatted display string for TEXT columns.

    Best-effort without parsing styles: if the cell is a percentage, append '%'
    after converting fraction to percent. Otherwise prefer the inline text if
    present; fall back to the raw value string.
    """
    if cell.value is None and (cell.text.strip() == ''):
        return None
    vtype = (cell.vtype or '').lower() if cell.vtype else ''
    # First, if the document provided an explicit display text, use it verbatim
    # (preserves locale-specific separators and spacing like NBSP before '%').
    if cell.text and cell.text.strip() != '':
        return cell.text
    if vtype == 'percentage' and cell.value is not None:
        try:
            # Determine desired decimal places from style mapping if available
            dp_count: Optional[int] = None
            if cell.style_name and cell.style_name in _STYLE_CELL_TO_DATA:
                dname = _STYLE_CELL_TO_DATA[cell.style_name]
                if dname in _STYLE_PERCENT_DECIMALS:
                    dp_count = _STYLE_PERCENT_DECIMALS[dname]
            # Convert fraction to percent and round per style, else default to 2
            if dp_count is None:
                dp_count = 2
            exp = Decimal('1') if dp_count == 0 else Decimal('0.' + '0' * (dp_count - 1) + '1')
            pct = (Decimal(cell.value) * Decimal(100)).quantize(exp, rounding=ROUND_HALF_UP)
            # Build string and then trim trailing zeros/decimal point
            s = format(pct, 'f')
            if '.' in s:
                s = s.rstrip('0').rstrip('.')
            # Determine decimal point and spacing per current locale
            try:
                dp = locale.localeconv().get('decimal_point') or '.'
            except Exception:
                dp = '.'
            if dp != '.':
                s = s.replace('.', dp)
                space = '\xa0'  # NBSP before % in many locales
            else:
                space = ''
            return s + space + '%'
        except Exception:
            pass
    # Fallback: stringify the raw value
    if cell.value is None:
        return None
    return str(cell.value)


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
            tables.append(
                TableSpec(
                    sheet=sheet_name, name=current_name, columns=col_defs[:], rows=data_rows[:]
                )
            )
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
                # row[1] may be Cell
                name_cell = row[1] if len(row) > 1 else None
                name_val = None
                if isinstance(name_cell, Cell):
                    name_val = (
                        name_cell.value if isinstance(name_cell.value, str) else name_cell.text
                    )
                else:
                    name_val = name_cell
                current_name = str(name_val or '').strip()
                if not current_name:
                    msg = f"[WARN] Sheet '{sheet_name}': {CONTROL_SQLTABLE} row missing table name; block ignored."
                    print(msg, file=stderr)
                    current_name = None
                continue
            if current_name is None:
                # ignore rows until a CONTROL_SQLTABLE marker is found
                continue
            if _is_keyword(first, KW_SQLCOLUMN):
                headers: list[str] = []
                for c in row[1:]:
                    if isinstance(c, Cell):
                        s = c.value if isinstance(c.value, str) else c.text
                        headers.append((str(s).strip() if s is not None else ''))
                    else:
                        headers.append((str(c).strip() if c is not None else ''))
                col_indices = [i for i, h in enumerate(headers) if h != '']
                if not col_indices:
                    msg = f"[WARN] Sheet '{sheet_name}', table '{current_name}': empty columns row; block ignored."
                    print(msg, file=stderr)
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
                    msg = f"[WARN] Sheet '{sheet_name}', table '{current_name}': {CONTROL_SQLTYPE} before columns row; using TEXT."
                    print(msg, file=stderr)
                types: list[str] = []
                for c in row[1:]:
                    if isinstance(c, Cell):
                        s = c.value if isinstance(c.value, str) else c.text
                        types.append((str(s).strip() if s is not None else ''))
                    else:
                        types.append((str(c).strip() if c is not None else ''))
                for idx, (name, _) in enumerate(col_defs):
                    t = types[col_indices[idx]] if col_indices[idx] < len(types) else ''
                    col_defs[idx] = (name, t or 'TEXT')
                continue
            # Data row: first cell empty
            is_empty_first = False
            if first is None:
                is_empty_first = True
            elif isinstance(first, Cell):
                v = first.value
                s = first.text
                is_empty_first = (v is None or (isinstance(v, str) and v.strip() == '')) and (
                    s.strip() == ''
                )
            elif isinstance(first, str):
                is_empty_first = first.strip() == ''
            else:
                is_empty_first = False
            if is_empty_first:
                if not col_defs:
                    # data before columns row
                    continue
                values = []
                # pick selected indices, offset by +1 because col 0 is the control column
                for i in col_indices:
                    j = 1 + i
                    v = row[j] if j < len(row) else None
                    if isinstance(v, Cell):
                        # Choose display string for TEXT columns when available/desired
                        col_type = (
                            col_defs[len(values)][1] if len(values) < len(col_defs) else 'TEXT'
                        )
                        if (col_type or '').strip().upper().startswith('TEXT'):
                            values.append(_cell_for_text_display(v))
                        else:
                            values.append(v.value)
                    else:
                        values.append(v)
                # Skip fully empty data rows
                if all(v is None or (isinstance(v, str) and v.strip() == '') for v in values):
                    continue
                data_rows.append(values)
                continue
            # Any other keyword starts a new block implicitly
            first_str = None
            if isinstance(first, Cell):
                first_str = first.value if isinstance(first.value, str) else first.text
            elif isinstance(first, str):
                first_str = first
            if isinstance(first_str, str) and first_str.strip() != '':
                flush()
                current_name = None
                # then re-process this row in case it's another CONTROL_SQLTABLE
                if _is_keyword(first, KW_SQLTABLE):
                    name_cell = row[1] if len(row) > 1 else None
                    if isinstance(name_cell, Cell):
                        nm = name_cell.value if isinstance(name_cell.value, str) else name_cell.text
                    else:
                        nm = name_cell
                    current_name = str(nm or '').strip()
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
            return '%.15g' % v
        # Everything else as string
        s = str(v)
        return "'" + s.replace("'", "''") + "'"

    def create_table(
        self,
        name: str,
        cols: list[tuple[str, str]],
        if_not_exists: bool,
        primary_key: Optional[list[str]] = None,
    ) -> str:
        ine = ' IF NOT EXISTS' if if_not_exists else ''
        colsql = ', '.join(f'{self.qid(cn)} {ct}' for cn, ct in cols)
        pk = ''
        if primary_key:
            pkcols = ', '.join(self.qid(c) for c in primary_key)
            pk = f', PRIMARY KEY ({pkcols})'
        return f'CREATE TABLE{ine} {self.qid(name)} ({colsql}{pk});'

    def drop_table(self, name: str) -> str:
        return f'DROP TABLE IF EXISTS {self.qid(name)};'

    def insert_many(self, name: str, cols: list[str], rows: list[list[object]]) -> str:
        csql = ', '.join(self.qid(c) for c in cols)
        values_sql = ', '.join('(' + ', '.join(self.lit(v) for v in r) + ')' for r in rows)
        return f'INSERT INTO {self.qid(name)} ({csql}) VALUES {values_sql};'

    def create_index(
        self, index_name: str, table: str, columns: list[str], if_not_exists: bool
    ) -> str:
        # IF NOT EXISTS is supported by sqlite & postgres, not by mysql
        ine = ''
        if if_not_exists and self.name in ('sqlite', 'postgres'):
            ine = ' IF NOT EXISTS'
        cols_sql = ', '.join(self.qid(c) for c in columns)
        return f'CREATE INDEX{ine} {self.qid(index_name)} ON {self.qid(table)} ({cols_sql});'


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
    p = argparse.ArgumentParser(
        description='Extract SQL from instrumented .ods spreadsheets (pure stdlib).',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument('ods', help='Path to .ods file')
    p.add_argument(
        '--dialect',
        choices=['sqlite', 'postgres', 'postgresql', 'mysql'],
        default='sqlite',
        help='SQL dialect for quoting & booleans',
    )
    p.add_argument(
        '--if-not-exists',
        action='store_true',
        help='Use IF NOT EXISTS in CREATE TABLE/INDEX (where supported)',
    )
    p.add_argument('--no-drop', action='store_true', help='Do not emit DROP TABLE IF EXISTS')
    p.add_argument('--schema-only', action='store_true', help='Emit only CREATE TABLE statements')
    p.add_argument('--data-only', action='store_true', help='Emit only INSERT statements')
    p.add_argument(
        '--batch',
        type=int,
        default=500,
        help='Rows per INSERT statement (0/1 for one row per INSERT)',
    )
    p.add_argument(
        '--table',
        action='append',
        default=[],
        help='Only export tables with this name (may repeat)',
    )
    p.add_argument(
        '--list', action='store_true', help='List detected tables & columns to stderr and exit'
    )
    p.add_argument(
        '--transaction',
        action='store_true',
        help='Wrap output in a single transaction (SQLite/Postgres)',
    )
    p.add_argument('--no-indices', action='store_true', help='Do not create any indices')
    p.add_argument(
        '--index-columns',
        default='',
        help='Comma-separated list of column names to index (defaults to all columns)',
    )
    p.add_argument(
        '--index',
        action='append',
        default=[],
        help='Define an index: columns separated by + (e.g., --index "col1+col2"). May repeat.',
    )
    p.add_argument(
        '--primary-key',
        default='',
        help='Comma-separated column name(s) for a PRIMARY KEY (omit for none)',
    )
    p.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity (stderr)')
    p.add_argument('--version', action='version', version=f'ods2sql.py {__version__}')
    return p.parse_args(argv)


def read_content_xml(ods_path: str) -> bytes:
    try:
        with zipfile.ZipFile(ods_path, 'r') as z:
            return z.read('content.xml')
    except KeyError:
        raise ODSParseError(
            'content.xml not found in .ods (is this a valid LibreOffice Calc file?)'
        )
    except FileNotFoundError:
        raise ODSParseError(f'File not found: {ods_path}')


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        content = read_content_xml(args.ods)
        # Build style maps (percentage decimal places, data-style-name mapping)
        _build_style_maps(content)
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
                msg = f'[INFO] {t.sheet}:{t.name}  cols={len(t.columns)} rows={len(t.rows)}'
                print(msg, file=sys.stderr)

        # Filter by --table if provided
        if args.table:
            wanted = set(args.table)
            tables = [t for t in tables if t.name in wanted]
            if not tables:
                print('[WARN] After filtering, no tables remained.', file=sys.stderr)
                return 0

        if args.list:
            for t in tables:
                cols = ', '.join(f'{n} {ty}' for n, ty in t.columns)
                msg = f'- {t.name}  (sheet: {t.sheet}) columns: {cols} rows: {len(t.rows)}'
                print(msg, file=sys.stderr)
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
                    msg = f"[WARN] Table '{t.name}': unknown PRIMARY KEY columns: {', '.join(unknown_pk)}"
                    print(msg, file=sys.stderr)
                    pk_cols = [c for c in pk_cols if c in col_names]
            if not args.data_only:
                if not args.no_drop:
                    print(dialect.drop_table(t.name), file=out)
                stmt = dialect.create_table(t.name, t.columns, args.if_not_exists, pk_cols or None)
                print(stmt, file=out)
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
                            msg = f"[WARN] Table '{t.name}': unknown columns in index '{spec}': {', '.join(unknown)}"
                            print(msg, file=sys.stderr)
                            cols = [c for c in cols if c in col_names]
                        if not cols:
                            continue
                        # MySQL cannot index TEXT/BLOB without prefix length; skip with a warning.
                        if dialect.name == 'mysql':
                            tb_cols = [
                                c
                                for c in cols
                                if 'text' in col_types.get(c, '').lower()
                                or 'blob' in col_types.get(c, '').lower()
                            ]
                            if tb_cols:
                                msg = f"[WARN] Table '{t.name}': skipping MySQL index on TEXT/BLOB columns: {', '.join(tb_cols)}"
                                print(msg, file=sys.stderr)
                                continue
                        # Skip if equal to PK columns set (ignoring order) to avoid redundancy
                        if pk_cols and set(cols) == set(pk_cols):
                            continue
                        key = tuple(cols)
                        if key in seen_indexes:
                            continue
                        seen_indexes.add(key)
                        iname = _limit_identifier(
                            f"idx_{_slug(t.name)}_{_slug('_'.join(cols))}", dialect.name
                        )
                        idx_stmt = dialect.create_index(iname, t.name, cols, args.if_not_exists)
                        print(idx_stmt, file=out)

                    # 2) Simple per-column indexes (legacy/default behavior)
                    if args.index_columns.strip():
                        desired = [c.strip() for c in args.index_columns.split(',') if c.strip()]
                        unknown = [c for c in desired if c not in col_names]
                        if unknown:
                            msg = f"[WARN] Table '{t.name}': unknown columns for indexing: {', '.join(unknown)}"
                            print(msg, file=sys.stderr)
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
                                msg = f"[WARN] Table '{t.name}': skipping MySQL index on TEXT/BLOB column: {c}"
                                print(msg, file=sys.stderr)
                                continue
                        key = (c,)
                        if key in seen_indexes:
                            continue
                        seen_indexes.add(key)
                        iname = _limit_identifier(f'idx_{_slug(t.name)}_{_slug(c)}', dialect.name)
                        idx_stmt_single = dialect.create_index(
                            iname, t.name, [c], args.if_not_exists
                        )
                        print(idx_stmt_single, file=out)
            if not args.schema_only and t.rows:
                batch = max(1, args.batch)
                if args.batch <= 1:
                    batch = 1
                for i in range(0, len(t.rows), batch):
                    chunk = t.rows[i : i + batch]
                    print(dialect.insert_many(t.name, col_names, chunk), file=out)

        if args.transaction and dialect.name in ('sqlite', 'postgres'):
            print('COMMIT;', file=out)
        return 0

    except ODSParseError as e:
        print('[ERROR]', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

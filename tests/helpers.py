from zipfile import ZipFile
from xml.etree.ElementTree import Element, SubElement, tostring
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, TypedDict

NS: Dict[str, str] = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
}


def q(ns: str, tag: str) -> str:
    return f'{{{NS[ns]}}}{tag}'


class CellSpec(TypedDict, total=False):
    value: object
    vtype: Optional[str]
    cols_repeat: int
    covered: bool


def make_cell(
    parent: Element,
    value: Optional[object] = None,
    *,
    vtype: Optional[str] = None,
    cols_repeat: int = 1,
    covered: bool = False,
) -> Element:
    tag = 'covered-table-cell' if covered else 'table-cell'
    cell = SubElement(parent, q('table', tag))
    if cols_repeat > 1:
        cell.set(q('table', 'number-columns-repeated'), str(cols_repeat))
    if vtype:
        cell.set(q('office', 'value-type'), vtype)
        if vtype in ('float', 'currency', 'percentage'):
            cell.set(q('office', 'value'), str(value))
        elif vtype == 'boolean':
            cell.set(q('office', 'boolean-value'), 'true' if value else 'false')
        elif vtype == 'date':
            cell.set(q('office', 'date-value'), str(value))
        elif vtype == 'time':
            cell.set(q('office', 'time-value'), str(value))
    if not covered and (vtype is None or vtype == 'string'):
        p = SubElement(cell, q('text', 'p'))
        p.text = '' if value is None else str(value)
    return cell


def make_row(table_el: Element, values: Sequence[Any], *, rows_repeat: int = 1) -> Element:
    row = SubElement(table_el, q('table', 'table-row'))
    if rows_repeat > 1:
        row.set(q('table', 'number-rows-repeated'), str(rows_repeat))
    for v in values:  # v can be plain or dict with {value, vtype, cols_repeat, covered}
        if isinstance(v, dict):
            cv = v.get('value')
            vt = v.get('vtype') if 'vtype' in v else None
            cr = int(v.get('cols_repeat', 1) or 1)
            cov = bool(v.get('covered', False))
            make_cell(row, cv, vtype=vt, cols_repeat=cr, covered=cov)
        else:
            make_cell(row, v, vtype='string')
    return row


def write_ods(path: Path, sheet_name: str, rows: Sequence[Any]) -> Path:
    doc = Element(q('office', 'document-content'), {f'xmlns:{k}': v for k, v in NS.items()})
    body = SubElement(doc, q('office', 'body'))
    sheet = SubElement(
        SubElement(body, q('office', 'spreadsheet')),
        q('table', 'table'),
        {q('table', 'name'): sheet_name},
    )
    for r in rows:
        make_row(sheet, r)
    xml = tostring(doc, encoding='utf-8', xml_declaration=True)
    with ZipFile(path, 'w') as z:
        z.writestr('content.xml', xml)
    return path

"""Read an indicator workbook (.xlsx) into rows.

The sheet is found by its header row: the first row, in the first 20 rows of any
sheet, that names at least an indicator, a target or achieved column and two
of period / location / sex. Column names are matched loosely
(see config.COLUMN_NAMES), so "Actual", "Department" and "Gender" work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .config import COLUMN_NAMES, Config

ALL_WORDS = {"all", "total", "both", "overall", "-", "", "n/a", "na", "combined", "national", "all locations"}
FEMALE = {"f", "female", "females", "women", "woman", "girls", "girl", "w"}
MALE = {"m", "male", "males", "men", "man", "boys", "boy"}
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth"}
MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
               "october", "november", "december"]


@dataclass
class Cell:
    ref: str          # "Indicators!H12"
    column: str       # "H"
    row: int
    value: float | None


@dataclass
class Row:
    excel_row: int
    indicator_id: str
    indicator: str
    unit: str          # canonical unit
    unit_label: str    # as written in the workbook
    period: str
    location: str      # "" when the row is an all-locations total
    sex: str           # female | male | all
    age: str           # children | adults | older | all
    target: Cell
    achieved: Cell
    values: list       # the raw row, for rendering


@dataclass
class Indicator:
    id: str
    name: str
    unit: str
    unit_label: str
    rate: bool
    has_sex: bool
    has_target: bool
    locations: list[str] = field(default_factory=list)
    has_age: bool = False


@dataclass
class Item:
    code: str
    name: str
    ppb: int           # pieces per box


@dataclass
class SheetRow:
    excel_row: int
    fields: dict       # field name -> text value
    cells: dict        # field name -> Cell, for numeric fields
    values: list


@dataclass
class Sheet:
    """A dispatch summary or stock sheet."""
    name: str
    header_row: int
    headers: list[str]
    columns: dict[str, int]
    rows: list[SheetRow]


@dataclass
class Workbook:
    path: str
    sheet: str
    header_row: int
    headers: list[str]
    columns: dict[str, int]          # field -> 1-based column index
    rows: list[Row]
    indicators: dict[str, Indicator]
    periods: list[str]               # oldest first
    locations: list[str]
    dispatch: Sheet | None = None
    stock: Sheet | None = None
    items: dict = field(default_factory=dict)        # item code -> Item
    warehouses: list[str] = field(default_factory=list)
    destinations: list[str] = field(default_factory=list)

    @property
    def current_period(self) -> str:
        return self.periods[-1]

    @property
    def previous_period(self) -> str | None:
        return self.periods[-2] if len(self.periods) > 1 else None

    def column_letter(self, field_name: str) -> str:
        return get_column_letter(self.columns[field_name])


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _match_header(cell) -> str | None:
    c = _norm(cell)
    for fname, names in COLUMN_NAMES.items():
        if c in names:
            return fname
    return None


def period_key(p: str):
    """Sortable key for 'Q3 2026', '2026 Q3', 'Q3-2026', 'July to September 2026'."""
    s = _norm(p)
    q = re.search(r"q([1-4])", s)
    y = re.search(r"(20\d{2}|19\d{2})", s)
    year = int(y.group(1)) if y else 0
    if q:
        return (year, int(q.group(1)))
    for i, name in enumerate(MONTH_NAMES):
        if name in s:
            return (year, i // 3 + 1)
    return (year, 0)


def period_phrases(p: str) -> list[str]:
    """Ways a narrative may name this period."""
    year, q = period_key(p)
    if not q:
        return [_norm(p)]
    first, last = MONTH_NAMES[(q - 1) * 3], MONTH_NAMES[(q - 1) * 3 + 2]
    out = [f"q{q}", f"{ORDINAL[q]} quarter", f"{first} to {last}", f"{first}-{last}", f"{first}–{last}",
           f"{first[:3]}-{last[:3]}", f"{first} and {last}"]
    return out


def read_workbook(path: str | Path, cfg: Config) -> Workbook:
    wb = load_workbook(str(path), data_only=True)
    for ws in wb.worksheets:
        for r in range(1, min(ws.max_row, 20) + 1):
            found = {}
            for c in range(1, ws.max_column + 1):
                f = _match_header(ws.cell(row=r, column=c).value)
                if f and f not in found:
                    found[f] = c
            need = {"indicator", "achieved"}
            if need <= set(found) and len({"period", "location", "sex", "target"} & set(found)) >= 2:
                book = _read_rows(path, ws, r, found, cfg)
                _read_stock_sheets(wb, book)
                return book
    raise ValueError("no indicator table found: need columns like Indicator, Target, Achieved, Period, "
                     "Location, Sex in the first 20 rows of a sheet")


def _num(cell) -> float | None:
    v = cell.value
    if v is None or v == "":
        return None
    if isinstance(v, str):
        v = v.replace(",", "").replace("%", "").strip()
        try:
            v = float(v)
        except ValueError:
            return None
    v = float(v)
    if "%" in (cell.number_format or "") and abs(v) <= 1.5:
        v *= 100.0
    return v


def _read_rows(path, ws, header_row, cols, cfg: Config) -> Workbook:
    rows: list[Row] = []
    headers = [str(ws.cell(row=header_row, column=c).value or "") for c in range(1, ws.max_column + 1)]
    tl = get_column_letter(cols["target"]) if "target" in cols else None
    al = get_column_letter(cols["achieved"])
    for r in range(header_row + 1, ws.max_row + 1):
        def get(f):
            return ws.cell(row=r, column=cols[f]).value if f in cols else None
        name = get("indicator")
        if not name:
            continue
        unit_label = str(get("unit") or "")
        if not unit_label and re.search(r"\(%\)|%$", str(name)):
            unit_label = "%"
        unit = cfg.canonical_unit(unit_label or "count")
        loc = str(get("location") or "").strip()
        if _norm(loc) in ALL_WORDS:
            loc = ""
        sx = _norm(get("sex"))
        sex = "female" if sx in FEMALE else "male" if sx in MALE else "all"
        ag = _norm(get("age"))
        age = ("children" if "child" in ag or ag.startswith("0") else "adults" if "adult" in ag else
               "older" if ("older" in ag or "elder" in ag or "60" in ag) else "all")
        tcell = ws.cell(row=r, column=cols["target"]) if "target" in cols else None
        acell = ws.cell(row=r, column=cols["achieved"])
        rows.append(Row(
            excel_row=r,
            indicator_id=str(get("indicator_id") or name).strip(),
            indicator=str(name).strip(),
            unit=unit, unit_label=unit_label,
            period=str(get("period") or "").strip(),
            location=loc, sex=sex, age=age,
            target=Cell(f"{ws.title}!{tl}{r}", tl, r, _num(tcell)) if tcell is not None else
            Cell("", "", r, None),
            achieved=Cell(f"{ws.title}!{al}{r}", al, r, _num(acell)),
            values=[ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)],
        ))
    indicators: dict[str, Indicator] = {}
    for row in rows:
        ind = indicators.get(row.indicator_id)
        if ind is None:
            ind = indicators[row.indicator_id] = Indicator(row.indicator_id, row.indicator, row.unit, row.unit_label,
                                                           row.unit == "percent", False, False)
        if row.sex != "all":
            ind.has_sex = True
        if row.age != "all":
            ind.has_age = True
        if row.target.value is not None:
            ind.has_target = True
        if row.location and row.location not in ind.locations:
            ind.locations.append(row.location)
    periods = sorted({r.period for r in rows if r.period}, key=period_key)
    locations = []
    for r in rows:
        if r.location and r.location not in locations:
            locations.append(r.location)
    return Workbook(str(path), ws.title, header_row, headers, cols, rows, indicators, periods or [""], locations)


DISPATCH_COLUMNS = {
    "period": ["period", "reporting period", "quarter"],
    "month": ["month", "dispatch month"],
    "item_code": ["item code", "code", "sku"],
    "item": ["item", "item name", "description", "item description"],
    "ppb": ["pieces per box", "pcs per box", "units per box", "pieces/box", "box size"],
    "warehouse": ["warehouse", "from warehouse", "source warehouse"],
    "destination": ["destination", "to", "consignee", "recipient"],
    "destination_type": ["destination type", "recipient type"],
    "pieces": ["pieces dispatched", "quantity dispatched (pieces)", "quantity (pieces)", "pieces", "quantity"],
}
STOCK_COLUMNS = {
    "period": ["period", "reporting period", "quarter"],
    "warehouse": ["warehouse"],
    "item_code": ["item code", "code", "sku"],
    "item": ["item", "item name", "description", "item description"],
    "ppb": ["pieces per box", "pcs per box", "units per box", "pieces/box", "box size"],
    "opening": ["opening balance", "opening", "opening stock"],
    "received_purchase": ["received (purchase)", "received purchase", "received (purchased)", "purchased"],
    "received_inkind": ["received (in-kind)", "received in kind", "received (in kind)", "in-kind", "donated"],
    "received": ["received", "total received"],
    "dispatched": ["dispatched", "issued", "dispatched (pieces)"],
    "closing": ["closing balance", "closing", "balance", "closing stock"],
}
NUMERIC = {"ppb", "pieces", "opening", "received_purchase", "received_inkind", "received", "dispatched", "closing"}


def _find(ws, names: dict, need: set):
    for r in range(1, min(ws.max_row, 20) + 1):
        found = {}
        for c in range(1, ws.max_column + 1):
            v = _norm(ws.cell(row=r, column=c).value)
            for f, alts in names.items():
                if v in alts and f not in found:
                    found[f] = c
        if need <= set(found):
            return r, found
    return None


def _read_sheet(ws, header_row, cols) -> Sheet:
    headers = [str(ws.cell(row=header_row, column=c).value or "") for c in range(1, ws.max_column + 1)]
    rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        if all(ws.cell(row=r, column=c).value in (None, "") for c in cols.values()):
            continue
        fields, cells = {}, {}
        for f, c in cols.items():
            cell = ws.cell(row=r, column=c)
            if f in NUMERIC:
                letter = get_column_letter(c)
                cells[f] = Cell(f"{ws.title}!{letter}{r}", letter, r, _num(cell))
            else:
                fields[f] = str(cell.value or "").strip()
        rows.append(SheetRow(r, fields, cells, [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]))
    return Sheet(ws.title, header_row, headers, cols, rows)


def _read_stock_sheets(wb, book: Workbook) -> None:
    """Find a dispatch summary sheet and a stock sheet, if the workbook has them."""
    for ws in wb.worksheets:
        if ws.title == book.sheet:
            continue
        hit = _find(ws, DISPATCH_COLUMNS, {"item", "destination", "pieces"})
        if hit and book.dispatch is None:
            book.dispatch = _read_sheet(ws, *hit)
            continue
        hit = _find(ws, STOCK_COLUMNS, {"item", "warehouse", "closing"})
        if hit and book.stock is None:
            book.stock = _read_sheet(ws, *hit)
    for sheet in (book.dispatch, book.stock):
        if sheet is None:
            continue
        for row in sheet.rows:
            code = row.fields.get("item_code") or row.fields.get("item")
            ppb = row.cells["ppb"].value if "ppb" in row.cells and row.cells["ppb"].value else 1
            if code not in book.items:
                book.items[code] = Item(code, row.fields.get("item", code), int(ppb))
            wh = row.fields.get("warehouse")
            if wh and wh not in book.warehouses:
                book.warehouses.append(wh)
            dest = row.fields.get("destination")
            if dest and dest not in book.destinations:
                book.destinations.append(dest)

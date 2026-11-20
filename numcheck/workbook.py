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
                return _read_rows(path, ws, r, found, cfg)
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
        tcell = ws.cell(row=r, column=cols["target"]) if "target" in cols else None
        acell = ws.cell(row=r, column=cols["achieved"])
        rows.append(Row(
            excel_row=r,
            indicator_id=str(get("indicator_id") or name).strip(),
            indicator=str(name).strip(),
            unit=unit, unit_label=unit_label,
            period=str(get("period") or "").strip(),
            location=loc, sex=sex,
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

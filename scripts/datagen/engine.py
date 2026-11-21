"""Engine for the synthetic quarterly donor reports of "the Organization".

The Organization is an unnamed humanitarian organization in Lebanon; every figure, project,
warehouse, partner and shelter here is invented. A report module defines indicators, stock
items, warehouses, workbook values and a narrative template. The template marks every number:

  {name}              a claim; `name` is a key in the module's CLAIMS dict
  [[text|kind]]       fixed text containing a number; kind is a non-claim kind (date, year,
                      section, phone, page, code, duration, age, period, word, measure,
                      threshold) or "unverifiable" for a claim the workbook does not record

Blocks are ("title"|"meta"|"h1"|"h2"|"p", template) or ("table", {"headers": [...], "rows": [[...]]}).
A table row becomes one narrative block whose text is "Header: cell | Header: cell", which is
also how numcheck reads Word tables.

The workbook has three sheets: Indicators, Dispatch summary and Stock.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

NONCLAIM_KINDS = {"date", "year", "section", "phone", "page", "code", "duration", "age", "period", "word",
                  "measure", "threshold"}
SEX = {"F": "Female", "M": "Male", "A": "All"}
AGE = {"CH": "Children (0-17)", "AD": "Adults (18-59)", "OL": "Older people (60+)", "A": "All"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] + ("-" + ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return ONES[h] + " hundred" + (" and " + words(r) if r else "")
    raise ValueError(n)


@dataclass
class Indicator:
    id: str
    name: str
    unit: str
    sex: bool = False
    age: bool = False
    rate: bool = False
    has_target: bool = True


@dataclass
class Item:
    code: str
    name: str
    ppb: int          # pieces per box


@dataclass
class Row:            # Indicators sheet
    ind: str
    period: str
    loc: str
    sex: str
    age: str
    target: float | None
    achieved: float
    excel_row: int = 0


@dataclass
class DRow:           # Dispatch summary sheet
    period: str
    month: str
    item: Item
    wh: str
    dest: str
    dest_type: str
    pieces: int
    excel_row: int = 0


@dataclass
class SRow:           # Stock sheet
    period: str
    wh: str
    item: Item
    opening: int
    recv_purchase: int
    recv_inkind: int
    dispatched: int
    closing: int
    excel_row: int = 0


IND_COLS = ("Indicator ID", "Indicator", "Unit", "Period", "{loc}", "Sex", "Age group", "Target", "Achieved")
DSP_COLS = ("Period", "Month", "Item code", "Item", "Pieces per box", "Warehouse", "Destination",
            "Destination type", "Pieces dispatched")
STK_COLS = ("Period", "Warehouse", "Item code", "Item", "Pieces per box", "Opening balance",
            "Received (purchase)", "Received (in-kind)", "Dispatched", "Closing balance")
STOCK_LETTER = {"opening": "F", "received_purchase": "G", "received_inkind": "H", "dispatched": "I", "closing": "J"}


class Data:
    def __init__(self, mod, ind_rows, dsp_rows, stk_rows):
        self.mod = mod
        self.ind = {i.id: i for i in mod.INDICATORS}
        self.locations = mod.LOCATIONS
        self.prev, self.cur = mod.PERIODS
        self.rows, self.drows, self.srows = ind_rows, dsp_rows, stk_rows
        for rows in (ind_rows, dsp_rows, stk_rows):
            for n, r in enumerate(rows, start=5):   # header on row 4
                r.excel_row = n

    def _periods(self, p):
        return {"cur": [self.cur], "prev": [self.prev], "cum": [self.prev, self.cur]}[p]

    # -- indicators
    def select(self, ind, period="cur", loc=None, sex=None, age=None):
        i = self.ind[ind]
        periods = self._periods(period)
        if i.rate:
            locs, sexes, ages = [loc or "All"], ["A"], ["A"]
        else:
            locs = [loc] if loc else self.locations
            sexes = ([sex] if sex else ["F", "M"]) if i.sex else ["A"]
            ages = ([age] if age else ["CH", "AD", "OL"]) if i.age else ["A"]
        out = [r for r in self.rows if r.ind == ind and r.period in periods and r.loc in locs
               and r.sex in sexes and r.age in ages]
        assert out, (ind, period, loc, sex, age)
        return out

    def query_ind(self, spec, period=None, loc="same", target_from=None):
        q = dict(period=period or spec.get("period", "cur"), loc=spec.get("loc") if loc == "same" else loc,
                 sex=spec.get("sex"), age=spec.get("age"))
        ind = spec["ind"]
        rows = self.select(ind, **q)
        ach = sum(r.achieved for r in rows)
        m = spec.get("measure", "achieved")
        if m == "achieved":
            return ach, [f"Indicators!I{r.excel_row}" for r in rows]
        if m == "target":
            return sum(r.target for r in rows), [f"Indicators!H{r.excel_row}" for r in rows]
        if m == "pct_target":
            trows = self.select(ind, **{**q, **(target_from or {})})
            cells = [f"Indicators!I{r.excel_row}" for r in rows] + [f"Indicators!H{r.excel_row}" for r in trows]
            return 100.0 * ach / sum(r.target for r in trows), cells
        if m == "share":
            allrows = self.select(ind, **{**q, "sex": None})
            cells = sorted({f"Indicators!I{r.excel_row}" for r in rows + allrows}, key=_cellkey)
            return 100.0 * ach / sum(r.achieved for r in allrows), cells
        raise ValueError(m)

    # -- dispatch summary
    def query_dispatch(self, spec, period=None):
        p = period or spec.get("period", "cur")
        rows = [r for r in self.drows if r.item.code == spec["item"] and r.period in self._periods(p)
                and (spec.get("wh") is None or r.wh == spec["wh"])
                and (spec.get("dest") is None or r.dest == spec["dest"])
                and (spec.get("month") is None or r.month.startswith(spec["month"]))]
        assert rows, spec
        pieces = sum(r.pieces for r in rows)
        cells = [f"Dispatch summary!I{r.excel_row}" for r in rows]
        if spec.get("measure", "pieces") == "boxes":
            return pieces / rows[0].item.ppb, cells
        return pieces, cells

    # -- stock
    def query_stock(self, spec, period=None):
        p = period or spec.get("period", "cur")
        rows = [r for r in self.srows if r.item.code == spec["item"] and r.period in self._periods(p)
                and (spec.get("wh") is None or r.wh == spec["wh"])]
        assert rows, spec
        m = spec["measure"]
        if m == "received":
            v = sum(r.recv_purchase + r.recv_inkind for r in rows)
            cells = [f"Stock!G{r.excel_row}" for r in rows] + [f"Stock!H{r.excel_row}" for r in rows]
            return v, sorted(cells, key=_cellkey)
        attr = {"opening": "opening", "received_purchase": "recv_purchase", "received_inkind": "recv_inkind",
                "dispatched": "dispatched", "closing": "closing"}[m]
        return sum(getattr(r, attr) for r in rows), [f"Stock!{STOCK_LETTER[m]}{r.excel_row}" for r in rows]

    def query(self, spec, **kw):
        src = spec.get("src", "ind")
        return {"ind": self.query_ind, "dispatch": self.query_dispatch, "stock": self.query_stock}[src](spec, **kw)

    def item(self, code) -> Item:
        return next(i for i in self.mod.ITEMS if i.code == code)


def _cellkey(c):
    m = re.search(r"([A-Z]+)(\d+)$", c)
    return (c.split("!")[0], int(m.group(2)), m.group(1))


# ---------------------------------------------------------------- building rows

def indicator_rows(ind: Indicator, periods, targets, rng, ach=(0.8, 1.02), female=(0.49, 0.56),
                   ages=(0.45, 0.42, 0.13)):
    """targets: {location: (previous-period target, current-period target)}."""
    rows = []
    for pi, period in enumerate(periods):
        for loc, pair in targets.items():
            tgt = pair[pi]
            got = round(tgt * rng.uniform(*ach))
            if ind.sex:
                tf, af = round(tgt * 0.52), round(got * rng.uniform(*female))
                parts = [("F", tf, af), ("M", tgt - tf, got - af)]
            else:
                parts = [("A", tgt, got)]
            for sx, st, sa in parts:
                if not ind.age:
                    rows.append(Row(ind.id, period, loc, sx, "A", st if ind.has_target else None, sa))
                    continue
                t_ch, t_ad = round(st * ages[0]), round(st * ages[1])
                a_ch = round(sa * rng.uniform(ages[0] - 0.03, ages[0] + 0.03))
                a_ad = round(sa * rng.uniform(ages[1] - 0.03, ages[1] + 0.03))
                for ag, vt, va in (("CH", t_ch, a_ch), ("AD", t_ad, a_ad), ("OL", st - t_ch - t_ad, sa - a_ch - a_ad)):
                    rows.append(Row(ind.id, period, loc, sx, ag, vt if ind.has_target else None, va))
    return rows


def dispatch_rows(items: dict, periods, routes, rng, loose=()):
    """routes: [(item code, warehouse, destination, destination type, pieces per month range in boxes)].
    Quantities are whole boxes except routes listed in `loose`, which get a remainder in pieces."""
    rows = []
    for period in periods:
        q = int(period[1])
        for mi in range(3):
            month = f"{MONTHS[(q - 1) * 3 + mi]} {period[-4:]}"
            for code, wh, dest, dtype, (lo, hi) in routes:
                it = items[code]
                pieces = rng.randint(lo, hi) * it.ppb
                if (code, dest) in loose and it.ppb > 1:
                    pieces += rng.randint(1, it.ppb - 1)
                rows.append(DRow(period, month, it, wh, dest, dtype, pieces))
    return rows


def stock_rows(items: dict, periods, drows, rng, openings, inkind=()):
    """One row per period, warehouse and item that appears in the dispatch rows.
    openings: {(warehouse, code): opening balance at the start of the first period}."""
    rows, balance = [], dict(openings)
    pairs = []
    for r in drows:
        if (r.wh, r.item.code) not in pairs:
            pairs.append((r.wh, r.item.code))
    for period in periods:
        for wh, code in pairs:
            it = items[code]
            out = sum(r.pieces for r in drows if r.period == period and r.wh == wh and r.item.code == code)
            opening = balance.get((wh, code), 0)
            need = max(0, out - opening)
            received = (math.ceil(need / it.ppb) + rng.randint(5, 60)) * it.ppb
            if (wh, code) in inkind:
                rin = (received // it.ppb // 2) * it.ppb
                rp = received - rin
            else:
                rin, rp = 0, received
            closing = opening + received - out
            rows.append(SRow(period, wh, it, opening, rp, rin, out, closing))
            balance[(wh, code)] = closing
    return rows


# ---------------------------------------------------------------- formats

def round_nice(v, direction):
    """Round to a 'round' number in the given direction, as a writer would."""
    for unit in (100000, 50000, 10000, 5000, 1000, 500, 100, 50, 10, 5):
        if unit > v / 3:
            continue
        r = (math.ceil(v / unit) if direction == "up" else math.floor(v / unit)) * unit
        if r != v and abs(r - v) / max(r, 1) <= 0.04:
            return r
    raise ValueError(f"no round number near {v}")


FRACTIONS = [(25.0, "a quarter"), (100 / 3, "a third"), (50.0, "half"), (200 / 3, "two thirds"),
             (75.0, "three quarters")]


def fmt_value(v, fmt, ppb=None):
    if fmt == "int":
        assert abs(v - round(v)) < 1e-9, f"not a whole number: {v}"
        return f"{round(v):,}"
    if fmt == "num0":
        return f"{round(v)}"
    if fmt == "word":
        return words(round(v))
    if fmt == "Word":
        return words(round(v)).capitalize()
    if fmt == "pct":
        return f"{round(v)} percent"
    if fmt == "pct%":
        return f"{round(v)}%"
    if fmt == "k1":
        return f"{v / 1000:.1f} thousand"
    if fmt == "nearly":
        return f"{round_nice(v, 'up'):,}"
    if fmt == "over":
        return f"{round_nice(v, 'down'):,}"
    if fmt == "about":
        up, down = round_nice(v, "up"), round_nice(v, "down")
        return f"{up if abs(up - v) <= abs(v - down) else down:,}"
    if fmt == "boxpcs":
        boxes, pcs = divmod(round(v), ppb)
        return f"{boxes:,} boxes and {pcs:,} piece{'s' if pcs != 1 else ''}" if pcs else f"{boxes:,} boxes"
    if fmt == "frac":
        return min(FRACTIONS, key=lambda f: abs(f[0] - v))[1]
    raise ValueError(fmt)


def transpose(s: str) -> str:
    """Swap the last pair of adjacent, different digits."""
    chars = list(s)
    idx = [i for i, c in enumerate(chars) if c.isdigit()]
    for a, b in reversed(list(zip(idx, idx[1:]))):
        if b == a + 1 and chars[a] != chars[b]:
            chars[a], chars[b] = chars[b], chars[a]
            return "".join(chars)
    raise ValueError(s)


# ---------------------------------------------------------------- rendering

TOKEN = re.compile(r"\{(\w+)\}|\[\[(.+?)\|(\w+)\]\]")


def render_template(template, block, base, claims, data, used, items):
    text, pos = "", 0
    for m in TOKEN.finditer(template):
        text += template[pos:m.start()]
        pos = m.end()
        start = base + len(text)
        if m.group(1):
            name = m.group(1)
            used.add(name)
            item = render_claim(name, claims[name], data)
            text += item["text"]
        else:
            raw, k = m.group(2), m.group(3)
            text += raw
            item = {"id": f"static-{len(items)}", "text": raw}
            if k == "unverifiable":
                item.update(kind="claim", status="unverifiable", error_type=None, expected_value=None, cells=[])
            else:
                assert k in NONCLAIM_KINDS, k
                item.update(kind="nonclaim", nonclaim_kind=k)
        item.update(block=block, start=start, end=base + len(text))
        items.append(item)
    return text + template[pos:]


def render(module, data: Data, out_dir: Path):
    claims = module.CLAIMS
    blocks, items, used = [], [], set()
    for kind, template in module.BLOCKS:
        if kind == "table":
            headers = template["headers"]
            rendered_rows = []
            for row in template["rows"]:
                text, cells = "", []
                for ci, (h, cell) in enumerate(zip(headers, row)):
                    if ci:
                        text += " | "
                    text += f"{h}: "
                    value = render_template(cell, len(blocks), len(text), claims, data, used, items)
                    cells.append(value)
                    text += value
                blocks.append({"kind": "row", "text": text})
                rendered_rows.append(cells)
            blocks[-len(rendered_rows)]["table"] = {"headers": headers, "rows": rendered_rows}
            continue
        text = render_template(template, len(blocks), 0, claims, data, used, items)
        blocks.append({"kind": kind, "text": text})
    missing = set(claims) - used
    assert not missing, f"unused claims: {missing}"
    check_unmarked(blocks, items)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_docx(blocks, out_dir / "report.docx")
    write_md(blocks, out_dir / "report.md")
    write_xlsx(data, out_dir / "indicators.xlsx", module.WORKBOOK_TITLE)
    gold = {"report": module.SLUG, "split": module.SPLIT, "title": blocks[0]["text"],
            "blocks": [b["text"] for b in blocks], "items": items}
    (out_dir / "gold.json").write_text(json.dumps(gold, indent=1), encoding="utf-8")
    return gold


def render_claim(name, spec, data: Data):
    value, cells = data.query(spec)
    fmt = spec.get("fmt", "int")
    ppb = data.item(spec["item"]).ppb if "item" in spec else None
    err = spec.get("error")
    if err is None:
        text = fmt_value(value, fmt, ppb)
    else:
        t = err["type"]
        if t == "previous_quarter":
            text = fmt_value(data.query(spec, period="prev")[0], fmt, ppb)
        elif t == "transposed":
            text = transpose(fmt_value(value, fmt, ppb))
        elif t == "wrong_target":
            text = fmt_value(data.query_ind(spec, target_from=err["target_from"])[0], fmt)
        elif t in ("split_sum", "district_total", "wrong_balance"):
            text = fmt_value(value + err["delta"], fmt, ppb)
        elif t == "hedge_overstates":
            text = f"{round_nice(value, 'up'):,}"
        elif t == "wrong_location":
            text = fmt_value(data.query_ind(spec, loc=err["loc"])[0], fmt)
        elif t == "pieces_as_boxes":       # spec counts boxes; the text gives the pieces figure
            assert spec["measure"] == "boxes"
            text = fmt_value(data.query({**spec, "measure": "pieces"})[0], "int")
        elif t == "boxes_as_pieces":       # spec counts pieces; the text gives the boxes figure
            text = fmt_value(data.query({**spec, "measure": "boxes"})[0], "int")
        elif t == "households_as_people":  # spec counts people; the text gives the household figure
            text = fmt_value(data.query_ind({**spec, "ind": err["ind"], "sex": None, "age": None})[0], fmt)
        else:
            raise ValueError(t)
        assert text != fmt_value(value, fmt, ppb), (name, text)
    return {"id": name, "text": text, "kind": "claim", "status": "inconsistent" if err else "consistent",
            "error_type": err["type"] if err else None, "expected_value": round(value, 4), "cells": cells,
            "spec": {k: v for k, v in spec.items() if k not in ("error", "fmt")}}


def check_unmarked(blocks, items):
    """Every digit in the narrative must belong to a marked item."""
    for bi, b in enumerate(blocks):
        covered = [(i["start"], i["end"]) for i in items if i["block"] == bi]
        for m in re.finditer(r"\d", b["text"]):
            if not any(s <= m.start() < e for s, e in covered):
                raise AssertionError(f"unmarked digit in block {bi}: {b['text'][max(0, m.start() - 30):m.start() + 30]!r}")


def write_docx(blocks, path: Path):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(8)
    style.paragraph_format.line_spacing = 1.15
    header = doc.sections[0].header.paragraphs[0]
    header.text = "The Organization (unnamed, fictional data). Synthetic document generated for testing."
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    for b in blocks:
        if b["kind"] == "row":
            if "table" in b:
                t = b["table"]
                table = doc.add_table(rows=1 + len(t["rows"]), cols=len(t["headers"]))
                table.style = "Table Grid"
                for ci, h in enumerate(t["headers"]):
                    cell = table.rows[0].cells[ci]
                    cell.text = h
                    cell.paragraphs[0].runs[0].bold = True
                for ri, row in enumerate(t["rows"], start=1):
                    for ci, v in enumerate(row):
                        table.rows[ri].cells[ci].text = v
                doc.add_paragraph("")
            continue
        if b["kind"] == "title":
            doc.add_heading(b["text"], level=0)
        elif b["kind"] in ("h1", "h2"):
            doc.add_heading(b["text"], level=int(b["kind"][1]))
        elif b["kind"] == "meta":
            doc.add_paragraph(b["text"]).runs[0].italic = True
        else:
            doc.add_paragraph(b["text"])
    doc.save(path)


def write_md(blocks, path: Path):
    lines = []
    for b in blocks:
        if b["kind"] == "row":
            if "table" in b:
                t = b["table"]
                lines.append("| " + " | ".join(t["headers"]) + " |")
                lines.append("|" + "---|" * len(t["headers"]))
                for row in t["rows"]:
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("")
            continue
        prefix = {"title": "# ", "h1": "## ", "h2": "### "}.get(b["kind"], "")
        text = f"*{b['text']}*" if b["kind"] == "meta" else b["text"]
        lines += [prefix + text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _sheet(wb, title, sheet_title, headers, widths, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = sheet_title
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Synthetic data for testing. The Organization, its projects, warehouses and partners are invented."
    ws["A2"].font = Font(italic=True, color="808080")
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F4858")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    return ws


def write_xlsx(data: Data, path: Path, title: str):
    mod = data.mod
    wb = Workbook()
    ws = _sheet(wb, title + ": indicator table", "Indicators", [h.format(loc=mod.LOC_HEADER) for h in IND_COLS],
                [12, 50, 11, 10, 24, 8, 18, 10, 10], first=True)
    for r in data.rows:
        ind = data.ind[r.ind]
        vals = [r.ind, ind.name, ind.unit, r.period, r.loc, SEX[r.sex], AGE[r.age], r.target, r.achieved]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=r.excel_row, column=c, value=v)
            if c >= 8 and v is not None:
                cell.number_format = "#,##0"
    ws = _sheet(wb, title + ": dispatch summary (from waybills)", "Dispatch summary", DSP_COLS,
                [10, 10, 13, 26, 9, 14, 30, 13, 11])
    for r in data.drows:
        vals = [r.period, r.month, r.item.code, r.item.name, r.item.ppb, r.wh, r.dest, r.dest_type, r.pieces]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=r.excel_row, column=c, value=v)
            if c == 9:
                cell.number_format = "#,##0"
    ws = _sheet(wb, title + ": stock by warehouse, in pieces", "Stock", STK_COLS,
                [10, 14, 13, 26, 9, 11, 11, 11, 11, 11])
    for r in data.srows:
        vals = [r.period, r.wh, r.item.code, r.item.name, r.item.ppb, r.opening, r.recv_purchase, r.recv_inkind,
                r.dispatched, r.closing]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=r.excel_row, column=c, value=v)
            if c >= 6:
                cell.number_format = "#,##0"
    wb.save(path)

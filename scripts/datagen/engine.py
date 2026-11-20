"""Engine for the synthetic Northbridge Relief reports.

A report module defines indicators, workbook values and a narrative template.
The template marks every number it contains:

  {name}              a claim; `name` is a key in the module's CLAIMS dict
  [[text|kind]]       a fixed piece of text with a number in it; kind is a
                      non-claim kind (date, year, section, phone, page, code,
                      duration, age, period, word) or "unverifiable" for a
                      claim that the workbook does not record

The engine renders the docx, the markdown copy, the xlsx and a gold file
listing every number with its expected result.
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
    sex: bool = False      # disaggregated by sex
    rate: bool = False     # a percentage, with an "All" location row
    has_target: bool = True


@dataclass
class Row:
    ind: str
    period: str
    loc: str
    sex: str
    target: float | None
    achieved: float
    excel_row: int = 0


@dataclass
class Layout:
    """Workbook layout; varies between reports on purpose."""
    sheet: str = "Indicators"
    headers: tuple = ("Indicator ID", "Indicator", "Unit", "Period", "Location", "Sex", "Target", "Achieved")
    sex_labels: dict = field(default_factory=lambda: {"F": "Female", "M": "Male", "A": "All"})
    all_loc: str = "All"
    rate_as_fraction: bool = False


class Data:
    def __init__(self, indicators, locations, periods, rows, layout: Layout):
        self.ind = {i.id: i for i in indicators}
        self.indicators = indicators
        self.locations = locations
        self.prev, self.cur = periods
        self.rows = rows
        self.layout = layout
        r = 5  # header on row 4
        for row in rows:
            row.excel_row = r
            r += 1

    def _periods(self, p):
        return {"cur": [self.cur], "prev": [self.prev], "cum": [self.prev, self.cur]}[p]

    def select(self, ind, period="cur", loc=None, sex=None):
        i = self.ind[ind]
        periods = self._periods(period)
        if i.rate:
            locs = [loc or "All"]
            sexes = ["A"]
        else:
            locs = [loc] if loc else self.locations
            sexes = ([sex] if sex else ["F", "M"]) if i.sex else ["A"]
        out = [r for r in self.rows if r.ind == ind and r.period in periods and r.loc in locs and r.sex in sexes]
        assert out, (ind, period, loc, sex)
        return out

    def cell(self, row: Row, col: str) -> str:
        letter = "G" if col == "target" else "H"
        return f"{self.layout.sheet}!{letter}{row.excel_row}"

    def query(self, ind, period="cur", loc=None, sex=None, measure="achieved", target_from=None):
        rows = self.select(ind, period, loc, sex)
        ach = sum(r.achieved for r in rows)
        if measure == "achieved":
            return ach, [self.cell(r, "achieved") for r in rows]
        if measure == "target":
            return sum(r.target for r in rows), [self.cell(r, "target") for r in rows]
        if measure == "pct_target":
            trows = self.select(ind, **(target_from or {"period": period, "loc": loc, "sex": sex}))
            tgt = sum(r.target for r in trows)
            cells = [self.cell(r, "achieved") for r in rows] + [self.cell(r, "target") for r in trows]
            return 100.0 * ach / tgt, cells
        if measure == "share":
            allrows = self.select(ind, period, loc, None)
            tot = sum(r.achieved for r in allrows)
            cells = sorted({self.cell(r, "achieved") for r in rows + allrows}, key=_cellkey)
            return 100.0 * ach / tot, cells
        raise ValueError(measure)


def _cellkey(c):
    m = re.search(r"([A-Z]+)(\d+)$", c)
    return (int(m.group(2)), m.group(1))


def count_rows(ind: Indicator, periods, targets, rng, ach=(0.8, 1.02), female=(0.49, 0.56)):
    """targets: {location: (previous-period target, current-period target)}."""
    rows = []
    for pi, period in enumerate(periods):
        for loc, pair in targets.items():
            tgt = pair[pi]
            got = round(tgt * rng.uniform(*ach))
            if ind.sex:
                fshare = rng.uniform(*female)
                tf = round(tgt * 0.52)
                gf = round(got * fshare)
                rows.append(Row(ind.id, period, loc, "F", tf if ind.has_target else None, gf))
                rows.append(Row(ind.id, period, loc, "M", (tgt - tf) if ind.has_target else None, got - gf))
            else:
                rows.append(Row(ind.id, period, loc, "A", tgt if ind.has_target else None, got))
    return rows


def rate_rows(ind: Indicator, periods, locations, target, rng, ach=(58, 86)):
    rows = []
    for period in periods:
        vals = []
        for loc in locations:
            v = round(rng.uniform(*ach))
            vals.append(v)
            rows.append(Row(ind.id, period, loc, "A", target, v))
        rows.append(Row(ind.id, period, "All", "A", target, round(sum(vals) / len(vals))))
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


def fmt_value(v, fmt):
    if fmt == "int":
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
    if fmt == "percent_sign":
        return f"{round(v)} per cent"
    if fmt == "pct1":
        return f"{v:.1f} percent"
    if fmt == "k1":
        return f"{v / 1000:.1f} thousand"
    if fmt == "m2":
        return f"{v / 1e6:.2f} million"
    if fmt == "m1":
        return f"{v / 1e6:.1f} million"
    if fmt == "nearly":
        return f"{round_nice(v, 'up'):,}"
    if fmt == "over":
        return f"{round_nice(v, 'down'):,}"
    if fmt == "about":
        up, down = round_nice(v, "up"), round_nice(v, "down")
        return f"{up if abs(up - v) <= abs(v - down) else down:,}"
    if fmt in ("frac", "frac_over"):
        best = min(FRACTIONS, key=lambda f: abs(f[0] - v))
        if fmt == "frac_over":
            below = [f for f in FRACTIONS if f[0] < v]
            best = max(below, key=lambda f: f[0])
        return best[1]
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


def parse_rendered(text: str) -> float:
    t = text.replace(",", "")
    m = re.match(r"([\d.]+)\s*(thousand|million)?", t)
    v = float(m.group(1))
    return v * {"thousand": 1e3, "million": 1e6, None: 1}[m.group(2)]


# ---------------------------------------------------------------- rendering

TOKEN = re.compile(r"\{(\w+)\}|\[\[(.+?)\|(\w+)\]\]")


def render(module, data: Data, out_dir: Path, slug: str, split: str):
    claims = module.CLAIMS
    blocks, items, used = [], [], set()
    for kind, template in module.BLOCKS:
        text, pos = "", 0
        for m in TOKEN.finditer(template):
            text += template[pos:m.start()]
            pos = m.end()
            start = len(text)
            if m.group(1):
                name = m.group(1)
                used.add(name)
                spec = claims[name]
                item = render_claim(name, spec, data)
                text += item["text"]
                item.update(block=len(blocks), start=start, end=len(text))
            else:
                raw, k = m.group(2), m.group(3)
                text += raw
                item = {"id": f"static-{len(items)}", "text": raw, "block": len(blocks), "start": start,
                        "end": len(text)}
                if k == "unverifiable":
                    item.update(kind="claim", status="unverifiable", error_type=None, expected_value=None,
                                cells=[])
                else:
                    assert k in NONCLAIM_KINDS, k
                    item.update(kind="nonclaim", nonclaim_kind=k)
            items.append(item)
        text += template[pos:]
        blocks.append({"kind": kind, "text": text})
    missing = set(claims) - used
    assert not missing, f"unused claims: {missing}"
    check_unmarked(blocks, items)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_docx(blocks, out_dir / "report.docx")
    write_md(blocks, out_dir / "report.md")
    write_xlsx(data, out_dir / "indicators.xlsx", module.WORKBOOK_TITLE)
    gold = {"report": slug, "split": split, "title": blocks[0]["text"],
            "blocks": [b["text"] for b in blocks], "items": items}
    (out_dir / "gold.json").write_text(json.dumps(gold, indent=1), encoding="utf-8")
    return gold


def render_claim(name, spec, data: Data):
    q = dict(period=spec.get("period", "cur"), loc=spec.get("loc"), sex=spec.get("sex"),
             measure=spec.get("measure", "achieved"))
    value, cells = data.query(spec["ind"], **q)
    fmt = spec.get("fmt", "int")
    err = spec.get("error")
    status, shown = "consistent", value
    if err is None:
        text = fmt_value(value, fmt)
    else:
        status = "inconsistent"
        t = err["type"]
        if t == "previous_quarter":
            shown, _ = data.query(spec["ind"], **{**q, "period": "prev"})
            text = fmt_value(shown, fmt)
        elif t == "transposed":
            text = transpose(fmt_value(value, fmt))
        elif t == "wrong_target":
            shown, _ = data.query(spec["ind"], **q, target_from=err["target_from"])
            text = fmt_value(shown, fmt)
        elif t == "split_sum":
            shown = value - err.get("delta", 100)
            text = fmt_value(shown, fmt)
        elif t == "hedge_overstates":
            # a round number above the true value, used after "over"/"more than"
            shown = round_nice(value, "up")
            text = fmt_value(shown, fmt if fmt in ("m1", "m2", "k1") else "int")
        elif t == "wrong_location":
            shown, _ = data.query(spec["ind"], **{**q, "loc": err["loc"]})
            text = fmt_value(shown, fmt)
        else:
            raise ValueError(t)
        assert text != fmt_value(value, fmt), (name, text)
    return {"id": name, "text": text, "kind": "claim", "status": status,
            "error_type": err["type"] if err else None, "expected_value": round(value, 4),
            "cells": cells, "indicator": spec["ind"], "query": q}


DIGIT = re.compile(r"\d")


def check_unmarked(blocks, items):
    """Every digit in the narrative must belong to a marked item."""
    for bi, b in enumerate(blocks):
        covered = [(i["start"], i["end"]) for i in items if i["block"] == bi]
        for m in DIGIT.finditer(b["text"]):
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
    header.text = "Northbridge Relief (fictional organisation). Synthetic document generated for testing."
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    for b in blocks:
        if b["kind"] == "title":
            doc.add_heading(b["text"], level=0)
        elif b["kind"] == "h1":
            doc.add_heading(b["text"], level=1)
        elif b["kind"] == "h2":
            doc.add_heading(b["text"], level=2)
        elif b["kind"] == "meta":
            p = doc.add_paragraph(b["text"])
            p.runs[0].italic = True
        else:
            doc.add_paragraph(b["text"])
    doc.save(path)


def write_md(blocks, path: Path):
    lines = []
    for b in blocks:
        prefix = {"title": "# ", "h1": "## ", "h2": "### "}.get(b["kind"], "")
        text = f"*{b['text']}*" if b["kind"] == "meta" else b["text"]
        lines += [prefix + text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xlsx(data: Data, path: Path, title: str):
    lay = data.layout
    wb = Workbook()
    ws = wb.active
    ws.title = lay.sheet
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Synthetic data for testing. Northbridge Relief is a fictional organisation."
    ws["A2"].font = Font(italic=True, color="808080")
    for c, h in enumerate(lay.headers, start=1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F4858")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in data.rows:
        ind = data.ind[row.ind]
        loc = lay.all_loc if row.loc == "All" else row.loc
        vals = [row.ind, ind.name, ind.unit, row.period, loc, lay.sex_labels[row.sex], row.target, row.achieved]
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=row.excel_row, column=c, value=v)
            if c >= 7 and v is not None:
                if ind.rate and lay.rate_as_fraction:
                    cell.value = v / 100.0
                    cell.number_format = "0%"
                elif ind.unit.lower() in ("usd",):
                    cell.number_format = "#,##0"
                elif not ind.rate:
                    cell.number_format = "#,##0"
    widths = [12, 52, 11, 12, 18, 9, 11, 11]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    wb.save(path)

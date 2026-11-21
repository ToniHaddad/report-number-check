"""Render a checked report as one self-contained HTML page (no external files)."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .checks import Result, fmt_num
from .pipeline import Report

MEASURE_LABEL = {
    "achieved": "achieved",
    "target": "target",
    "pct_target": "percent of target (achieved / target)",
    "share": "share of the total",
    "rate": "percentage reported in the workbook",
}
SEX_LABEL = {"female": "women and girls", "male": "men and boys", None: "everyone (both sexes)"}


STOCK_MEASURE = {
    "dispatched": "dispatched", "received": "received (purchased and in kind)",
    "received_inkind": "received as in-kind donations", "received_purchase": "received from purchases",
    "opening": "opening balance", "closing": "closing balance",
}
AGE_LABEL = {"children": "children", "adults": "adults", "older": "older people"}


def _interp_dict(r: Result) -> dict:
    it = r.interp
    if it.source in ("dispatch", "stock") and it.item is not None:
        where = it.destinations[0] if it.destinations else "all destinations"
        return {
            "item": f"{it.item.code}: {it.item.name} ({it.item.ppb} per box)",
            "measure": STOCK_MEASURE.get(it.measure, it.measure) + f", in {it.unit}",
            "warehouse": it.warehouses[0] if it.warehouses else "all warehouses",
            "warehouse_how": it.location_how,
            "destination": where if it.source == "dispatch" else "",
            "period": it.months[0].title() if it.months else ", ".join(it.periods),
            "period_how": it.period_how,
            "via": it.via,
        }
    if it.indicator is None:
        return {}
    return {
        "indicator": f"{it.indicator.id}: {it.indicator.name}",
        "measure": MEASURE_LABEL.get(it.measure, it.measure) + (
            f" ({SEX_LABEL[it.sex]})" if it.measure == "share" else ""),
        "location": "all locations" if it.locations is None else ", ".join(it.locations),
        "location_how": it.location_how,
        "period": ", ".join(it.periods),
        "period_how": it.period_how,
        "sex": SEX_LABEL.get(it.sex, it.sex) if it.measure != "share" else "",
        "age": AGE_LABEL.get(it.age, "") if it.age else "",
        "via": it.via,
    }


def _fmt_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _sheet_payload(name, header_row, headers, columns, rows_by_n, used, show_fields, numeric_cols):
    from openpyxl.utils import get_column_letter
    shown = [columns[f] for f in show_fields if f in columns]
    rows = {}
    for n in used:
        row = rows_by_n.get(n)
        if row is None:
            continue
        rows[n] = [(_fmt_cell(row[i - 1]) if i in numeric_cols else ("" if row[i - 1] is None else str(row[i - 1])))
                   for i in range(1, len(headers) + 1)]
    return {"columns": [get_column_letter(i) for i in shown], "col_index": [i - 1 for i in shown],
            "headers": [headers[i - 1] for i in shown], "header_row": header_row, "rows": rows}


def report_payload(rep: Report) -> dict:
    wb = rep.workbook
    used = {}
    for r in rep.results:
        sheet = r.cells[0].get("sheet", wb.sheet) if r.cells else wb.sheet
        used.setdefault(sheet, set()).update(r.rows)
    sheets = {}
    # indicator sheet: values formatted, % for rates
    rows = {}
    tcol = wb.columns.get("target")
    acol = wb.columns["achieved"]
    for row in wb.rows:
        if row.excel_row not in used.get(wb.sheet, ()):
            continue
        vals = list(row.values)
        pct = "%" if row.unit == "percent" else ""
        vals[acol - 1] = fmt_num(row.achieved.value) + pct if row.achieved.value is not None else ""
        if tcol:
            vals[tcol - 1] = fmt_num(row.target.value) + pct if row.target.value is not None else ""
        rows[row.excel_row] = vals
    ind_fields = ["period", "location", "sex", "age", "target", "achieved"]
    sheets[wb.sheet] = _sheet_payload(wb.sheet, wb.header_row, wb.headers, wb.columns, rows,
                                      sorted(used.get(wb.sheet, ())), ind_fields, set())
    if wb.dispatch is not None:
        d = wb.dispatch
        sheets[d.name] = _sheet_payload(d.name, d.header_row, d.headers, d.columns,
                                        {r.excel_row: r.values for r in d.rows}, sorted(used.get(d.name, ())),
                                        ["month", "item", "warehouse", "destination", "pieces"],
                                        {d.columns.get("pieces"), d.columns.get("ppb")})
    if wb.stock is not None:
        st = wb.stock
        num = {st.columns.get(f) for f in ("opening", "received_purchase", "received_inkind", "received",
                                           "dispatched", "closing", "ppb")}
        sheets[st.name] = _sheet_payload(st.name, st.header_row, st.headers, st.columns,
                                         {r.excel_row: r.values for r in st.rows}, sorted(used.get(st.name, ())),
                                         ["warehouse", "item", "opening", "received_purchase", "received_inkind",
                                          "received", "dispatched", "closing"], num)
    claims = []
    for i, r in enumerate(rep.results):
        c = r.claim
        b = rep.blocks[c.block]
        s0, s1 = c.sentence
        sentence = b.text[s0:s1]
        claims.append({
            "i": i, "block": c.block, "status": r.status, "text": c.text,
            "value": c.value, "kind": c.kind, "hedge": c.hedge_text,
            "sentence": sentence, "s_from": c.start - s0, "s_to": c.end - s0, "in_table": b.kind == "row",
            "interp": _interp_dict(r), "reason": r.reason,
            "expected": None if r.expected is None else (
                f"{r.expected:.1f}%" if c.kind in ("percent", "fraction") else
                fmt_num(round(r.expected, 2)) + (" boxes" if r.interp.unit == "boxes" and c.extra_pieces is None
                                                 and r.interp.source != "indicators" else
                                                 " pieces" if r.interp.source != "indicators" else "")),
            "calculation": r.calculation, "tolerance": r.tolerance,
            "sheet": r.cells[0].get("sheet", wb.sheet) if r.cells else wb.sheet,
            "cells": [{"ref": x["ref"], "col": x["column"], "row": x["row"], "role": x["role"]} for x in r.cells],
            "rows": r.rows, "hints": r.hints, "notes": r.notes,
        })
    return {
        "title": next((b.text for b in rep.blocks if b.kind == "heading"), Path(rep.narrative_path).name),
        "narrative": Path(rep.narrative_path).name,
        "workbook": Path(rep.workbook_path).name,
        "period": wb.current_period,
        "counts": rep.counts,
        "sheets": sheets,
        "claims": claims,
    }


def _marked(text: str, start: int, end: int, items) -> str:
    """HTML for text[start:end] with claim buttons inserted."""
    parts, pos = [], start
    for i, r in items:
        c = r.claim
        if c.start < pos or c.end > end:
            continue
        parts.append(html.escape(text[pos:c.start]))
        label = {"consistent": "Consistent", "inconsistent": "Inconsistent", "unverifiable": "Unverifiable"}[r.status]
        parts.append(f'<button type="button" class="claim s-{r.status}" data-i="{i}" '
                     f'aria-label="{label}: {html.escape(c.text)}">{html.escape(text[c.start:c.end])}</button>')
        pos = c.end
    parts.append(html.escape(text[pos:end]))
    return "".join(parts)


def _narrative_html(rep: Report) -> str:
    by_block: dict[int, list[tuple[int, Result]]] = {}
    for i, r in enumerate(rep.results):
        by_block.setdefault(r.claim.block, []).append((i, r))
    for v in by_block.values():
        v.sort(key=lambda x: x[1].claim.start)
    out, open_table = [], None
    for b in rep.blocks:
        items = by_block.get(b.index, [])
        if b.kind == "row":
            if open_table != b.table:
                if open_table is not None:
                    out.append("</tbody></table></div>")
                out.append('<div class="doc-table-wrap"><table class="doc-table"><thead><tr>'
                           + "".join(f"<th>{html.escape(h)}</th>" for h in b.headers) + "</tr></thead><tbody>")
                open_table = b.table
            cells = "".join(f"<td>{_marked(b.text, s, e, items)}</td>" for s, e in b.cells)
            out.append(f"<tr>{cells}</tr>")
            continue
        if open_table is not None:
            out.append("</tbody></table></div>")
            open_table = None
        inner = _marked(b.text, 0, len(b.text), items)
        if b.kind == "heading":
            tag = {0: "h1", 1: "h2"}.get(b.level, "h3")
            out.append(f"<{tag}>{inner}</{tag}>")
        else:
            out.append(f"<p>{inner}</p>")
    if open_table is not None:
        out.append("</tbody></table></div>")
    return "\n".join(out)


def render_html(rep: Report, toolbar: str = "") -> str:
    payload = report_payload(rep)
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    counts = payload["counts"]
    total = max(1, sum(counts.values()))
    return (TEMPLATE
            .replace("{{TITLE}}", html.escape(payload["title"]))
            .replace("{{NARRATIVE_FILE}}", html.escape(payload["narrative"]))
            .replace("{{WORKBOOK_FILE}}", html.escape(payload["workbook"]))
            .replace("{{PERIOD}}", html.escape(payload["period"]))
            .replace("{{N_OK}}", str(counts["consistent"]))
            .replace("{{N_BAD}}", str(counts["inconsistent"]))
            .replace("{{N_UNK}}", str(counts["unverifiable"]))
            .replace("{{W_OK}}", f"{100 * counts['consistent'] / total:.2f}")
            .replace("{{W_BAD}}", f"{100 * counts['inconsistent'] / total:.2f}")
            .replace("{{W_UNK}}", f"{100 * counts['unverifiable'] / total:.2f}")
            .replace("{{TOOLBAR}}", toolbar)
            .replace("{{NARRATIVE}}", _narrative_html(rep))
            .replace("{{DATA}}", data))


def write_html(rep: Report, path: str | Path) -> None:
    Path(path).write_text(render_html(rep), encoding="utf-8")


TEMPLATE = (Path(__file__).parent / "static" / "review.html").read_text(encoding="utf-8")

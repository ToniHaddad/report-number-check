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


def _interp_dict(r: Result) -> dict:
    it = r.interp
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
        "via": it.via,
    }


def report_payload(rep: Report) -> dict:
    wb = rep.workbook
    used_rows = sorted({row for r in rep.results for row in r.rows})
    rows = {}
    by_row = {row.excel_row: row for row in wb.rows}
    tcol = wb.columns.get("target")
    acol = wb.columns["achieved"]
    for n in used_rows:
        row = by_row.get(n)
        if row is None:
            continue
        vals = []
        for ci, v in enumerate(row.values, start=1):
            if ci == acol:
                vals.append(fmt_num(row.achieved.value) + ("%" if row.unit == "percent" else "")
                            if row.achieved.value is not None else "")
            elif tcol and ci == tcol:
                vals.append(fmt_num(row.target.value) + ("%" if row.unit == "percent" else "")
                            if row.target.value is not None else "")
            else:
                vals.append("" if v is None else str(v))
        rows[n] = vals
    from openpyxl.utils import get_column_letter
    # The indicator name and unit are shown above the table; leave them out so the
    # target and achieved columns fit without scrolling.
    hidden = {wb.columns.get("indicator"), wb.columns.get("unit"), wb.columns.get("indicator_id")}
    shown_cols = [i for i in range(1, len(wb.headers) + 1) if i not in hidden and wb.headers[i - 1]]
    claims = []
    for i, r in enumerate(rep.results):
        c = r.claim
        block = rep.blocks[c.block].text
        s0, s1 = c.sentence
        claims.append({
            "i": i, "block": c.block, "status": r.status, "text": c.text,
            "value": c.value, "kind": c.kind, "hedge": c.hedge_text,
            "sentence": block[s0:s1], "s_from": c.start - s0, "s_to": c.end - s0,
            "interp": _interp_dict(r), "reason": r.reason,
            "expected": None if r.expected is None else (
                f"{r.expected:.1f}%" if c.kind in ("percent", "fraction") else fmt_num(r.expected)),
            "calculation": r.calculation, "tolerance": r.tolerance,
            "cells": [{"ref": x["ref"], "col": x["column"], "row": x["row"], "role": x["role"]} for x in r.cells],
            "rows": r.rows, "hints": r.hints, "notes": r.notes,
        })
    return {
        "title": next((b.text for b in rep.blocks if b.kind == "heading"), Path(rep.narrative_path).name),
        "narrative": Path(rep.narrative_path).name,
        "workbook": Path(rep.workbook_path).name,
        "sheet": wb.sheet,
        "period": wb.current_period,
        "counts": rep.counts,
        "columns": [get_column_letter(i) for i in shown_cols],
        "col_index": [i - 1 for i in shown_cols],
        "headers": [wb.headers[i - 1] for i in shown_cols],
        "header_row": wb.header_row,
        "rows": rows,
        "claims": claims,
    }


def _narrative_html(rep: Report) -> str:
    by_block: dict[int, list[tuple[int, Result]]] = {}
    for i, r in enumerate(rep.results):
        by_block.setdefault(r.claim.block, []).append((i, r))
    out = []
    for b in rep.blocks:
        text = b.text
        parts, pos = [], 0
        for i, r in sorted(by_block.get(b.index, []), key=lambda x: x[1].claim.start):
            c = r.claim
            if c.start < pos:
                continue
            parts.append(html.escape(text[pos:c.start]))
            label = {"consistent": "Consistent", "inconsistent": "Inconsistent",
                     "unverifiable": "Unverifiable"}[r.status]
            parts.append(f'<button type="button" class="claim s-{r.status}" data-i="{i}" '
                         f'aria-label="{label}: {html.escape(c.text)}">{html.escape(text[c.start:c.end])}</button>')
            pos = c.end
        parts.append(html.escape(text[pos:]))
        inner = "".join(parts)
        if b.kind == "heading":
            tag = {0: "h1", 1: "h2"}.get(b.level, "h3")
            out.append(f"<{tag}>{inner}</{tag}>")
        else:
            out.append(f"<p>{inner}</p>")
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

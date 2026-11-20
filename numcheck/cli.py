"""Command line: numcheck check report.docx indicators.xlsx --out review.html"""
from __future__ import annotations

import argparse
import json
import sys

from .checks import fmt_num
from .pipeline import check
from .render import write_html


def _summary(rep) -> str:
    c = rep.counts
    lines = [f"{rep.narrative_path} vs {rep.workbook_path} (sheet '{rep.workbook.sheet}', "
             f"period checked {rep.workbook.current_period})",
             f"{sum(c.values())} figures: {c['inconsistent']} inconsistent, {c['unverifiable']} unverifiable, "
             f"{c['consistent']} consistent", ""]
    for r in rep.results:
        if r.status != "inconsistent":
            continue
        cl = r.claim
        block = rep.blocks[cl.block].text
        sent = block[cl.sentence[0]:cl.sentence[1]]
        exp = f"{r.expected:.1f}%" if cl.kind in ("percent", "fraction") and r.expected is not None \
            else fmt_num(r.expected) if r.expected is not None else "-"
        lines.append(f"INCONSISTENT  {cl.text!r}  workbook: {exp}")
        lines.append(f"    sentence: {sent}")
        if r.interp.indicator:
            loc = "all locations" if r.interp.locations is None else ", ".join(r.interp.locations)
            lines.append(f"    read as:  {r.interp.indicator.id} {r.interp.measure}, {loc}, {', '.join(r.interp.periods)}"
                         + (f", {r.interp.sex}" if r.interp.sex else ""))
        if r.calculation:
            lines.append(f"    calc:     {r.calculation}")
        for h in r.hints:
            lines.append(f"    hint:     {h}")
        for n in r.notes:
            lines.append(f"    note:     {n}")
        lines.append("")
    return "\n".join(lines)


def _json(rep) -> dict:
    out = []
    for r in rep.results:
        it = r.interp
        out.append({
            "text": r.claim.text, "status": r.status, "value": r.claim.value, "kind": r.claim.kind,
            "hedge": r.claim.hedge, "expected": r.expected, "calculation": r.calculation, "reason": r.reason,
            "cells": [c["ref"] for c in r.cells], "hints": r.hints, "notes": r.notes,
            "indicator": it.indicator.id if it.indicator else None, "measure": it.measure,
            "locations": it.locations, "periods": it.periods, "sex": it.sex,
        })
    return {"counts": rep.counts, "claims": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="numcheck", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a narrative report against an indicator workbook")
    c.add_argument("narrative", help=".docx or .md report")
    c.add_argument("workbook", help=".xlsx indicator table")
    c.add_argument("--out", help="write the review page (a single HTML file) here")
    c.add_argument("--json", help="write all results as JSON here")
    c.add_argument("--config", help="matching rules (default: the bundled matching.toml)")
    c.add_argument("-q", "--quiet", action="store_true", help="print only the one-line summary")
    s = sub.add_parser("serve", help="run the review page on http://127.0.0.1:8110")
    s.add_argument("--port", type=int, default=8110)
    s.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("numcheck.app:app", host=args.host, port=args.port)
        return 0

    try:
        rep = check(args.narrative, args.workbook, args.config)
    except (OSError, ValueError) as e:
        print(f"numcheck: {e}", file=sys.stderr)
        return 2
    text = _summary(rep)
    print(text.splitlines()[1] if args.quiet else text.rstrip())
    if args.out:
        write_html(rep, args.out)
        print(f"review page written to {args.out}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(_json(rep), f, indent=1)
    return 1 if rep.counts["inconsistent"] else 0


if __name__ == "__main__":
    sys.exit(main())

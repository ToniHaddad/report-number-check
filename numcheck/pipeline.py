"""Run a full check: narrative + workbook -> results."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from .checks import Result, fmt_num, hints_for, lookup, lookup_stock, within
from .config import Config, load_config
from .matcher import Context, Interpretation, Matcher
from .narrative import Block, read_narrative
from .numbers import Claim, extract_claims
from .text import clauses, sentences
from .workbook import Workbook, read_workbook


@dataclass
class Report:
    narrative_path: str
    workbook_path: str
    blocks: list[Block]
    workbook: Workbook
    results: list[Result]

    @property
    def counts(self) -> dict[str, int]:
        out = {"consistent": 0, "inconsistent": 0, "unverifiable": 0}
        for r in self.results:
            out[r.status] += 1
        return out


def check(narrative: str | Path, workbook: str | Path, config: str | None = None) -> Report:
    cfg: Config = copy.deepcopy(load_config(config))
    wb = read_workbook(workbook, cfg)
    blocks = read_narrative(narrative)
    matcher = Matcher(wb, cfg)
    results: list[Result] = []
    for block in blocks:
        results.extend(_check_block(block, wb, cfg, matcher))
    _derived_checks(results)
    _stock_arithmetic(results, wb)
    return Report(str(narrative), str(workbook), blocks, wb, results)


def _check_block(block: Block, wb: Workbook, cfg: Config, matcher: Matcher) -> list[Result]:
    text = block.text
    claims = extract_claims(text, block.index, cfg, is_heading=block.kind == "heading")
    if not claims:
        return []
    is_row = block.kind == "row"
    sents = [(0, len(text))] if is_row else (sentences(text) or [(0, len(text))])
    out, resolved = [], {}
    prev_text, prev_claims = "", []
    for si, (ss, se) in enumerate(sents):
        last = si == len(sents) - 1
        sc = [c for c in claims if ss <= c.num_start < (se if not last else len(text) + 1)]
        cl = list(block.cells) if is_row else clauses(text, ss, se)
        if is_row:   # a cell's clause starts at its header: "Pieces dispatched: 1,832"
            cl = [(text.rfind("|", 0, a) + 1 if text.rfind("|", 0, a) >= 0 else 0, b) for a, b in cl]
        for c in sc:
            c.sentence = (ss, se)
            c.clause = next(((a, b) for a, b in cl if a <= c.num_start < b), (ss, se))
        for c in sc:
            ctx = Context(claim=c, block_text=text, sentence=text[ss:se], sentence_start=ss,
                          clause=text[c.clause[0]:c.clause[1]], clause_start=c.clause[0],
                          prev_sentence=prev_text, heading=block.heading if block.kind in ("paragraph", "row") else "",
                          sentence_claims=sc, is_row=is_row)
            it = matcher.interpret(ctx, resolved, prev_claims)
            resolved[c.id] = it
            out.append(evaluate(c, it, wb, cfg))
            out[-1].sentence_index = si
        prev_text, prev_claims = text[ss:se], sc
    return out


def evaluate(c: Claim, it: Interpretation, wb: Workbook, cfg: Config) -> Result:
    if it.unverifiable:
        return Result(c, it, "unverifiable", reason=it.unverifiable)
    lk = lookup_stock(wb, it) if it.source in ("dispatch", "stock") else lookup(wb, it)
    if lk.problem or lk.value is None:
        return Result(c, it, "unverifiable", reason=lk.problem or "no value", cells=lk.cells, rows=lk.rows)
    if c.extra_pieces is not None:      # "12 boxes and 6 pieces": compare in pieces
        if it.unit == "boxes":
            lk = lookup_stock(wb, it, unit="pieces")
        stated = c.value * it.item.ppb + c.extra_pieces if it.item else c.value
        ok = abs(stated - lk.value) < 1e-6
        tol = f"{fmt_num(c.value)} boxes x {it.item.ppb} + {c.extra_pieces} = {fmt_num(stated)} pieces" if it.item else ""
    elif it.source in ("dispatch", "stock") and it.unit == "boxes":
        ok = abs(c.value - lk.value) < 1 - 1e-9 if c.hedge is None else within(c, lk.value, cfg)[0]
        tol = "whole boxes: within one box of the pieces divided by pieces per box" if c.hedge is None else \
            within(c, lk.value, cfg)[1]
    else:
        ok, tol = within(c, lk.value, cfg)
    r = Result(c, it, "consistent" if ok else "inconsistent", expected=lk.value, calculation=lk.calculation,
               tolerance=tol, cells=lk.cells, rows=lk.rows)
    if not ok:
        r.hints = hints_for(r, wb, cfg)
    return r


def _derived_checks(results: list[Result]) -> None:
    """Arithmetic inside the text: women + men = total, locations add up to the total."""
    by_block: dict[int, list[Result]] = {}
    for r in results:
        by_block.setdefault(r.claim.block, []).append(r)
    for rs in by_block.values():
        matched = [r for r in rs if r.interp.indicator is not None and r.claim.kind in ("count", "money")
                   and r.interp.measure == "achieved" and r.claim.hedge is None]
        for total in matched:
            near = [r for r in matched if r is not total
                    and abs(r.sentence_index - total.sentence_index) <= 1
                    and r.interp.indicator.id == total.interp.indicator.id
                    and r.interp.periods == total.interp.periods]
            # sex split
            if total.interp.sex is None:
                parts = {}
                for r in near:
                    if r.interp.sex and r.interp.locations == total.interp.locations and r.interp.sex not in parts:
                        parts[r.interp.sex] = r
                if set(parts) == {"female", "male"}:
                    _apply_sum(total, [parts["female"], parts["male"]], "women/girls plus men/boys")
            # location split
            if total.interp.locations is None:
                locs = total.interp.indicator.locations
                parts = {}
                for r in near:
                    if r.interp.sex == total.interp.sex and r.interp.locations and len(r.interp.locations) == 1:
                        parts.setdefault(r.interp.locations[0], r)
                if locs and set(parts) == set(locs):
                    _apply_sum(total, [parts[loc] for loc in locs], "the locations")


def _apply_sum(total: Result, parts: list[Result], label: str) -> None:
    s = sum(p.claim.value for p in parts)
    expr = " + ".join(fmt_num(p.claim.value) for p in parts)
    if abs(s - total.claim.value) < 0.5:
        total.notes.append(f"Sum check in the text: {label} {expr} = {fmt_num(s)}, as stated.")
        return
    msg = (f"Sum check in the text: {label} {expr} = {fmt_num(s)}, but the stated total is "
           f"{fmt_num(total.claim.value)} (a gap of {fmt_num(abs(s - total.claim.value))}).")
    for r in [total] + parts:
        if msg not in r.notes:
            r.notes.append(msg)
        if r.status == "unverifiable" and r is not total:
            r.status = "inconsistent"
            r.reason = ""
            r.calculation = msg



def _stock_arithmetic(results: list[Result], wb: Workbook) -> None:
    """Stock arithmetic inside the text: opening + received - dispatched = the balance stated."""
    by_block: dict[int, list[Result]] = {}
    for r in results:
        it = r.interp
        if it.source in ("dispatch", "stock") and it.item is not None and r.claim.hedge is None                 and r.claim.extra_pieces is None and it.unit != "boxes":
            by_block.setdefault(r.claim.block, []).append(r)
    for rs in by_block.values():
        for bal in [r for r in rs if r.interp.measure == "closing"]:
            key = (bal.interp.item.code, tuple(bal.interp.warehouses or []), tuple(bal.interp.periods))
            near = [r for r in rs if r is not bal and abs(r.sentence_index - bal.sentence_index) <= 1
                    and (r.interp.item.code, tuple(r.interp.warehouses or []), tuple(r.interp.periods)) == key]
            got = {}
            for r in near:
                m = "received" if r.interp.measure.startswith("received") else r.interp.measure
                if m in ("opening", "received", "dispatched") and m not in got:
                    got[m] = r
            if "received" not in got or "dispatched" not in got:
                continue
            if "opening" in got:
                opening, o_label = got["opening"].claim.value, f"opening {fmt_num(got['opening'].claim.value)}"
            else:
                from .checks import lookup_stock
                import copy as _copy
                tmp = _copy.copy(bal.interp)
                tmp.source, tmp.measure = "stock", "opening"
                lk = lookup_stock(wb, tmp)
                if lk.value is None:
                    continue
                opening, o_label = lk.value, f"opening {fmt_num(lk.value)} (from the workbook)"
            rec, dsp = got["received"].claim.value, got["dispatched"].claim.value
            expect = opening + rec - dsp
            calc = f"{o_label} + received {fmt_num(rec)} - dispatched {fmt_num(dsp)} = {fmt_num(expect)}"
            if abs(expect - bal.claim.value) < 0.5:
                bal.notes.append(f"Stock arithmetic in the text: {calc}, as stated.")
            else:
                msg = (f"Stock arithmetic in the text: {calc}, but the stated balance is "
                       f"{fmt_num(bal.claim.value)}.")
                for r in [bal] + list(got.values()):
                    if msg not in r.notes:
                        r.notes.append(msg)

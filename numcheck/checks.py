"""Compute the workbook value a claim should equal, compare with tolerance, explain."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .matcher import Interpretation
from .numbers import Claim
from .workbook import Row, Workbook


@dataclass
class Lookup:
    value: float | None
    cells: list[dict]            # {"ref", "column", "row", "value", "role"}
    rows: list[int]              # excel rows used
    calculation: str
    problem: str | None = None


@dataclass
class Result:
    claim: Claim
    interp: Interpretation
    status: str                  # consistent | inconsistent | unverifiable
    reason: str = ""
    expected: float | None = None
    calculation: str = ""
    tolerance: str = ""
    cells: list[dict] = field(default_factory=list)
    rows: list[int] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sentence_index: int = 0


def fmt_num(v: float, pct: bool = False) -> str:
    if v is None:
        return "?"
    if pct:
        return f"{v:.1f}%"
    if abs(v - round(v)) < 1e-9:
        return f"{round(v):,}"
    return f"{v:,.2f}"


def _sum_expr(cells: list[dict]) -> str:
    refs = [c["column"] + str(c["row"]) for c in cells]
    if len(refs) > 6:
        return f"SUM of {len(refs)} cells ({refs[0]} ... {refs[-1]})"
    return " + ".join(refs)


def select_rows(wb: Workbook, it: Interpretation, sex: str | None, periods=None, locations="same"):
    ind = it.indicator
    periods = periods or it.periods
    locs = it.locations if locations == "same" else locations
    rows = [r for r in wb.rows if r.indicator_id == ind.id and r.period in periods]
    if not rows:
        return [], f"no rows for {ind.id} in {', '.join(periods)}"
    if locs is None:
        totals = [r for r in rows if r.location == ""]
        rows = totals if totals else [r for r in rows if r.location]
    else:
        rows = [r for r in rows if r.location in locs]
        if not rows:
            return [], f"no rows for {', '.join(locs)}"
    if sex:
        rows = [r for r in rows if r.sex == sex]
        if not rows:
            return [], f"no {sex} rows for {ind.id}"
    else:
        alls = [r for r in rows if r.sex == "all"]
        rows = alls if alls else rows
    return rows, None


def _cells(rows: list[Row], role: str) -> list[dict]:
    out = []
    for r in rows:
        c = r.target if role == "target" else r.achieved
        out.append({"ref": c.ref, "column": c.column, "row": c.row, "value": c.value, "role": role})
    return out


def lookup(wb: Workbook, it: Interpretation, periods=None, locations="same", target_periods=None,
           target_locations="same") -> Lookup:
    ind = it.indicator
    m = it.measure
    if ind.rate and len(periods or it.periods) > 1:
        return Lookup(None, [], [], "", "a percentage cannot be added up across periods")
    sex_for_rows = it.sex if m != "share" else it.sex
    rows, problem = select_rows(wb, it, sex_for_rows, periods, locations)
    if problem:
        return Lookup(None, [], [], "", problem)
    if ind.rate and len(rows) > 1:
        return Lookup(None, [], [], "", "several percentage rows match and cannot be combined")
    if m in ("achieved", "rate"):
        cells = _cells(rows, "achieved")
        if any(c["value"] is None for c in cells):
            return Lookup(None, cells, [r.excel_row for r in rows], "", "an empty achieved cell")
        v = sum(c["value"] for c in cells)
        calc = f"{_sum_expr(cells)} = {fmt_num(v, ind.rate)}" if len(cells) > 1 else \
            f"{cells[0]['column']}{cells[0]['row']} = {fmt_num(v, ind.rate)}"
        return Lookup(v, cells, [r.excel_row for r in rows], calc)
    if m == "target":
        cells = _cells(rows, "target")
        if any(c["value"] is None for c in cells):
            return Lookup(None, cells, [r.excel_row for r in rows], "", "no target in the workbook")
        v = sum(c["value"] for c in cells)
        calc = f"{_sum_expr(cells)} = {fmt_num(v, ind.rate)}" if len(cells) > 1 else \
            f"{cells[0]['column']}{cells[0]['row']} = {fmt_num(v, ind.rate)}"
        return Lookup(v, cells, [r.excel_row for r in rows], calc)
    if m == "pct_target":
        trows = rows
        if target_periods is not None or target_locations != "same":
            trows, problem = select_rows(wb, it, it.sex, target_periods or periods, target_locations)
            if problem:
                return Lookup(None, [], [], "", problem)
        a = _cells(rows, "achieved")
        t = _cells(trows, "target")
        if any(c["value"] is None for c in a + t):
            return Lookup(None, a + t, [r.excel_row for r in rows], "", "no target in the workbook")
        av, tv = sum(c["value"] for c in a), sum(c["value"] for c in t)
        if tv == 0:
            return Lookup(None, a + t, [], "", "target is zero")
        v = 100.0 * av / tv
        calc = (f"({_sum_expr(a)}) / ({_sum_expr(t)}) = {fmt_num(av)} / {fmt_num(tv)} = {v:.1f}%"
                if len(a) > 1 else f"{_sum_expr(a)} / {_sum_expr(t)} = {fmt_num(av)} / {fmt_num(tv)} = {v:.1f}%")
        return Lookup(v, a + t, sorted({r.excel_row for r in rows + trows}), calc)
    if m == "share":
        part, problem = select_rows(wb, it, it.sex, periods, locations)
        if problem:
            return Lookup(None, [], [], "", problem)
        whole, problem = select_rows(wb, it, None, periods, locations)
        if problem:
            return Lookup(None, [], [], "", problem)
        if all(r.sex == "all" for r in whole):
            pass
        else:
            whole = [r for r in whole if r.sex in ("female", "male")]
        p, w = _cells(part, "achieved"), _cells(whole, "achieved")
        if any(c["value"] is None for c in p + w):
            return Lookup(None, p + w, [], "", "an empty achieved cell")
        pv, wv = sum(c["value"] for c in p), sum(c["value"] for c in w)
        v = 100.0 * pv / wv
        allcells = {c["ref"]: c for c in p + w}
        calc = f"({_sum_expr(p)}) / ({_sum_expr(w)}) = {fmt_num(pv)} / {fmt_num(wv)} = {v:.1f}%"
        return Lookup(v, list(allcells.values()), sorted({r.excel_row for r in whole}), calc)
    return Lookup(None, [], [], "", f"unknown measure {m}")


def within(claim: Claim, actual: float, cfg: Config) -> tuple[bool, str]:
    """Is the workbook value consistent with the claim as written (rounding and hedge)?"""
    v = claim.value
    pct = claim.kind in ("percent", "fraction")
    unit = "%" if pct else ""
    if claim.kind == "fraction":
        h = claim.hedge
        tol = cfg.fraction_tol_hedged if h else cfg.fraction_tol
        lo, hi = {
            None: (v - tol, v + tol), "about": (v - tol, v + tol), "nearly": (v - tol, v),
            "over": (v, v + tol), "at_least": (v, v + tol), "under": (v - tol, v), "up_to": (v - tol, v),
        }.get(h, (v - tol, v + tol))
        ok = lo - 1e-9 <= actual <= hi + 1e-9
        if h in ("over",) and actual <= v:
            ok = False
        if h in ("under",) and actual >= v:
            ok = False
        return ok, f"'{claim.text}' allows {lo:.1f}% to {hi:.1f}%"
    if claim.hedge is None:
        lo, hi = v - claim.precision, v + claim.precision
        ok = lo - 1e-9 <= actual <= hi + 1e-9
        if claim.precision <= 0.5 and not pct:
            return ok, "exact figure: must match the workbook"
        return ok, f"as written, it rounds from {_f(lo, pct)} to {_f(hi, pct)}{unit}"
    h = cfg.hedges[claim.hedge]
    lo, hi = v * h["low"], v * h["high"]
    lo_ok = actual > lo if h.get("strict_low") else actual >= lo - 1e-9
    hi_ok = actual < hi if h.get("strict_high") else actual <= hi + 1e-9
    word = (claim.hedge_text or claim.hedge).strip()
    lo_s = ("more than " if h.get("strict_low") else "") + _f(lo, pct)
    hi_s = ("less than " if h.get("strict_high") else "") + _f(hi, pct)
    return lo_ok and hi_ok, f"'{word}' allows {lo_s} to {hi_s}{unit}"


def _f(v, pct):
    return f"{v:.1f}" if pct else f"{v:,.0f}"


def hints_for(result: Result, wb: Workbook, cfg: Config) -> list[str]:
    """Explain a mismatch: is the stated figure found elsewhere in the workbook?"""
    c, it = result.claim, result.interp
    out = []
    if it.indicator is None:
        return out

    def matches(v):
        return v is not None and within(c, v, cfg)[0]

    if it.measure in ("achieved", "rate", "target"):
        for p in wb.periods:
            if p in it.periods:
                continue
            lk = lookup(wb, it, periods=[p])
            if matches(lk.value):
                out.append(f"The stated figure is the {p} value ({lk.calculation}). Left over from an earlier report?")
        for loc in wb.indicators[it.indicator.id].locations:
            if it.locations == [loc]:
                continue
            lk = lookup(wb, it, locations=[loc])
            if matches(lk.value):
                out.append(f"The stated figure is the value for {loc} ({lk.calculation}).")
        if it.sex is None and it.indicator.has_sex:
            for sx in ("female", "male"):
                tmp = Interpretation(**{**it.__dict__, "sex": sx})
                lk = lookup(wb, tmp)
                if matches(lk.value):
                    out.append(f"The stated figure is the {sx} figure only ({lk.calculation}).")
    if it.measure == "pct_target":
        options = []
        for p in wb.periods:
            if [p] != it.periods:
                options.append((f"the {p} target", dict(target_periods=[p])))
        if len(wb.periods) > 1:
            options.append(("the target for all periods together", dict(target_periods=list(wb.periods))))
        for loc in wb.indicators[it.indicator.id].locations:
            if it.locations != [loc]:
                options.append((f"the {loc} target", dict(target_locations=[loc])))
        for label, kw in options:
            lk = lookup(wb, it, **kw)
            if matches(lk.value):
                out.append(f"The stated percentage matches achieved over {label}: {lk.calculation}. "
                           f"Worked out against the wrong target?")
    if result.expected is not None and not c.spelled and c.kind in ("count", "money"):
        exp, got = f"{round(result.expected)}", f"{round(c.value)}"
        if len(exp) == len(got) and sorted(exp) == sorted(got) and exp != got:
            diff = [i for i in range(len(exp)) if exp[i] != got[i]]
            if len(diff) == 2 and diff[1] == diff[0] + 1:
                out.append(f"Two digits look swapped: the workbook says {fmt_num(result.expected)}, "
                           f"the report says {fmt_num(c.value)}.")
    if c.hedge and result.expected is not None:
        if c.hedge in ("over", "at_least") and result.expected <= c.value:
            out.append(f"'{c.hedge_text}' overstates: the workbook value {fmt_num(result.expected)} is not above "
                       f"{fmt_num(c.value)}.")
        if c.hedge in ("nearly",) and result.expected > c.value:
            out.append(f"'{c.hedge_text}' means a little below, but the workbook value "
                       f"{fmt_num(result.expected)} is above {fmt_num(c.value)}.")
    return out

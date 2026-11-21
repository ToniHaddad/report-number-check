"""Measure the checker against the gold labels of the synthetic reports.

    python scripts/benchmark.py            # the two tuning reports only
    python scripts/benchmark.py --final    # also the held-out report
    python scripts/benchmark.py -v         # list every disagreement with the gold labels

The held-out report (WASH-2026) is excluded unless --final is given, so that it
is not looked at while the rules are being tuned.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from numcheck.pipeline import check  # noqa: E402


def evaluate(report_dir: Path, verbose: bool) -> Counter:
    gold = json.loads((report_dir / "gold.json").read_text(encoding="utf-8"))
    rep = check(report_dir / "report.docx", report_dir / "indicators.xlsx")
    tool_blocks = [b.text for b in rep.blocks]
    if tool_blocks != gold["blocks"]:
        raise SystemExit(f"{report_dir.name}: narrative blocks read from the docx differ from the gold file")
    m = Counter()
    used = set()
    lines = []
    for g in gold["items"]:
        hits = [r for r in rep.results if r.claim.block == g["block"]
                and r.claim.num_start < g["end"] and g["start"] < r.claim.num_end]
        r = hits[0] if hits else None
        if r is not None:
            used.add(id(r))
        if g["kind"] == "nonclaim":
            m["nonclaims"] += 1
            if r is not None:
                m["nonclaims_extracted"] += 1
                lines.append(f"  non-claim taken as a claim: {g['text']!r} ({g['nonclaim_kind']}) -> {r.status}")
            continue
        m["claims"] += 1
        got = r.status if r else "not extracted"
        gs = g["status"]
        m[f"gold_{gs}"] += 1
        m[f"gold_{gs}->{got}"] += 1
        if gs in ("consistent", "inconsistent"):
            m["verifiable"] += 1
            if r is not None and r.status != "unverifiable":
                m["attempted"] += 1
                if sorted(c["ref"] for c in r.cells) == sorted(g["cells"]):
                    m["right_cells"] += 1
                elif verbose:
                    lines.append(f"  wrong cells for {g['text']!r}: tool {[c['ref'] for c in r.cells]} "
                                 f"gold {g['cells']}")
        if gs == "inconsistent":
            m["planted"] += 1
            m["caught"] += got == "inconsistent"
            m["planted_passed_consistent"] += got == "consistent"
        if gs == "consistent" and got == "inconsistent":
            m["false_alarms"] += 1
        if gs == "unverifiable" and got == "inconsistent":
            m["false_alarms_unverifiable"] += 1
        if gs == "unverifiable" and got == "consistent":
            m["unsupported_passed_consistent"] += 1
        if got != gs:
            sent = ""
            if r is not None:
                b = rep.blocks[r.claim.block].text
                sent = b[r.claim.sentence[0]:r.claim.sentence[1]]
            why = ""
            if r is not None:
                why = r.reason or (r.hints[0] if r.hints else r.calculation)
            lines.append(f"  [{gs} -> {got}] {g['text']!r} ({g.get('error_type') or g['id']}) {why}\n"
                         f"      {sent}")
    for r in rep.results:
        if id(r) not in used:
            m["spurious"] += 1
            lines.append(f"  extracted but not in gold: {r.claim.text!r} -> {r.status}")
    if verbose and lines:
        print(f"\n{report_dir.name}")
        print("\n".join(lines))
    return m


def show(name: str, m: Counter) -> None:
    def pct(a, b):
        return f"{a}/{b}" + (f" ({100 * a / b:.0f}%)" if b else "")
    print(f"\n== {name} ==")
    print(f"  claims in gold                        {m['claims']}  (consistent {m['gold_consistent']}, "
          f"planted errors {m['gold_inconsistent']}, not in workbook {m['gold_unverifiable']})")
    print(f"  planted errors caught                 {pct(m['caught'], m['planted'])}")
    print(f"  wrong figures passed as consistent    {m['planted_passed_consistent']} planted errors, "
          f"{m['unsupported_passed_consistent']} claims with no workbook support")
    print(f"  false alarms                          {m['false_alarms']} of {m['gold_consistent']} correct "
          f"figures; {m['false_alarms_unverifiable']} of {m['gold_unverifiable']} figures not in the workbook")
    print(f"  correct figures confirmed             {pct(m['gold_consistent->consistent'], m['gold_consistent'])}")
    print(f"  correct figures left unverifiable     {m['gold_consistent->unverifiable']}")
    print(f"  claims matched to the right cell(s)   {pct(m['right_cells'], m['verifiable'])} of checkable claims"
          f" ({m['right_cells']}/{m['attempted']} of those the tool attempted)")
    print(f"  figures not extracted                 {sum(v for k, v in m.items() if k.endswith('->not extracted'))}")
    print(f"  non-claims ignored                    {pct(m['nonclaims'] - m['nonclaims_extracted'], m['nonclaims'])}")
    print(f"  numbers extracted that are not in gold {m['spurious']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="also run the held-out report")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    by_split: dict[str, Counter] = {}
    for d in sorted((ROOT / "data").iterdir()):
        if not (d / "gold.json").exists():
            continue
        split = json.loads((d / "gold.json").read_text(encoding="utf-8"))["split"]
        if split == "heldout" and not args.final:
            continue
        m = evaluate(d, args.verbose)
        show(f"{d.name} ({split})", m)
        by_split.setdefault(split, Counter()).update(m)
    for split, m in by_split.items():
        show(f"ALL {split.upper()} REPORTS", m)


if __name__ == "__main__":
    main()

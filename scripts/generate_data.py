"""Generate the synthetic quarterly donor reports with workbooks and gold labels.

    python scripts/generate_data.py

Writes data/<report>/report.docx, report.md, indicators.xlsx and gold.json.
Everything is deterministic (fixed random seeds). All names and figures are invented.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from datagen import emergency_appeal, food_assistance, wash_winter  # noqa: E402
from datagen.engine import Data, render  # noqa: E402

MODULES = [food_assistance, emergency_appeal, wash_winter]


def main() -> None:
    for mod in MODULES:
        data = Data(mod, *mod.build())
        gold = render(mod, data, ROOT / "data" / mod.SLUG)
        claims = [i for i in gold["items"] if i["kind"] == "claim"]
        words = sum(len(b.split()) for b in gold["blocks"])
        status = Counter(i["status"] for i in claims)
        errors = [i["error_type"] for i in claims if i["error_type"]]
        print(f"{mod.SLUG:28s} {mod.SPLIT:8s} {words:5d} words  claims={len(claims)} {dict(status)}  "
              f"non-claims={len(gold['items']) - len(claims)}  planted={errors}")


if __name__ == "__main__":
    main()

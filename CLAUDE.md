# report-number-check

Checks the figures in a narrative donor report (.docx or .md) against its indicator workbook (.xlsx).
Deterministic rules only: no LLM, no API key, no network. All data is synthetic (fictional Northbridge Relief).

## Run and test
- `python -m venv .venv`, then `pip install -e ".[dev]"`
- `numcheck check <report.docx> <indicators.xlsx> --out review.html` (exit 1 if anything inconsistent, 2 on bad input)
- `numcheck serve` runs the one-page app on port 8110 (use only that port)
- `pytest` for tests; `python scripts/benchmark.py` for the tuning reports, `--final` adds the held-out one
- `python scripts/generate_data.py` regenerates `data/` deterministically

## Layout
- `numcheck/numbers.py` extracts claims; `matcher.py` decides indicator, measure, location, period, sex;
  `checks.py` looks up cells, applies tolerance, writes hints; `pipeline.py` ties them together
- `numcheck/config/matching.toml` holds all vocabulary, hedge tolerances and the weak-match thresholds
- `numcheck/render.py` + `static/review.html` build the single-file review page (shared by CLI and app)
- `scripts/datagen/` holds the three report templates; claims are marked `{name}`, fixed numbers `[[text|kind]]`

## Rules and quirks
- Never let a weak match become "consistent": unclear matches must stay unverifiable. The benchmark counts
  wrong figures passed as consistent; keep it at 0.
- The Colombia report is held out. Do not tune rules on it; the README quotes a single run made at commit 4c79f6b.
  If rules change, rerun `--final` and report the new numbers as a second measurement, not a replacement.
- Every digit in a template must be marked, or the generator raises an error.
- The review template is read at import time: restart `numcheck serve` after editing it.
- On machines with application control, the `numcheck.exe` shim may be blocked; `python -m numcheck` works.

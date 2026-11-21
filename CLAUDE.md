# report-number-check

Checks the figures in a quarterly donor report (.docx or .md, including Word tables) against its workbook
(.xlsx): an indicator table, a dispatch summary and a stock sheet. Deterministic rules only: no LLM, no
API key, no network. All data is synthetic; the organization is unnamed ("the Organization" in samples).

## Run and test
- `python -m venv .venv`, then `pip install -e ".[dev]"`
- `numcheck check <report.docx> <indicators.xlsx> --out review.html` (exit 1 if anything inconsistent, 2 on bad input)
- `numcheck serve` runs the one-page app on port 8110 (use only that port)
- `pytest`; `python scripts/benchmark.py` for the tuning reports, `--final` adds the held-out one
- `python scripts/generate_data.py` regenerates `data/` deterministically

## Layout
- `numcheck/numbers.py` extracts claims; `matcher.py` interprets indicator figures; `stock.py` interprets
  dispatch and stock figures (item, warehouse, destination, month, measure, pieces or boxes);
  `checks.py` looks up cells, applies tolerance, writes hints; `pipeline.py` ties them together and runs
  the arithmetic checks inside the text (sums, stock balance)
- `numcheck/config/matching.toml` holds all vocabulary, hedge tolerances and the weak-match thresholds
- `numcheck/render.py` + `static/review.html` build the single-file review page (shared by CLI and app)
- `scripts/datagen/` holds the engine and the three report templates; claims are `{name}`, fixed numbers `[[text|kind]]`

## Rules and quirks
- Never let a weak match become "consistent": unclear matches stay unverifiable. Keep the benchmark's
  "wrong figures passed as consistent" at 0.
- `WASH-2026` (data/wash-2026-q3) is held out. Do not tune on it; the README quotes one run with rules frozen
  at 3137a11. If rules change, rerun `--final` and report it as a new measurement, not a replacement.
- Every digit in a template must be marked, or the generator raises an error. Spelled counts ("three
  sites") should be marked too, or they show up as extractions not in gold.
- The review template is read at import time: restart `numcheck serve` after editing it.
- On machines with application control, the `numcheck.exe` shim may be blocked; `python -m numcheck` works.
- The repo is public: invented names and figures only.

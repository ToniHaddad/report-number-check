# report-number-check

Finds the figures in a narrative donor report that disagree with the indicator, dispatch and stock records behind it.

![Review page: a food assistance report with every figure coloured by result; the selected figure, 1,896 "boxes" of canned cheese, is shown to be the number of pieces, with the matched dispatch cells](docs/review-desktop.png)

<sub>More screenshots: [phone](docs/review-mobile.png), [dark theme](docs/review-dark.png). All data shown is synthetic.</sub>

## The need

A humanitarian organization in Lebanon writes a quarterly report for each donor-funded project. The
narrative is written in Word by programme staff, but its figures come from records kept by other people:
the indicator table, and the warehouse records of what was received, dispatched on waybills and left in
stock, counted in pieces with boxes as a convenience. Figures go wrong on the way: 1,896 pieces of canned
cheese become "1,896 boxes", the household count is quoted as "people", a stock balance does not equal
received minus dispatched, a total across districts does not add up. Checking every number by hand takes
hours and is the first thing dropped at deadline.

## Try it

```
python -m venv .venv
.venv\Scripts\activate          # or: source .venv/bin/activate
pip install -e .
numcheck check data/fa-2026-q3/report.docx data/fa-2026-q3/indicators.xlsx --out review.html
```

(`python -m numcheck ...` does the same if your machine blocks new executables.) Real output, abridged
from [docs/sample-output.txt](docs/sample-output.txt):

```
44 figures: 7 inconsistent, 6 unverifiable, 31 consistent

INCONSISTENT  '3,513'  workbook: 16,697
    sentence: In total the project supported 3,513 people.
    read as:  FA-2 achieved, all locations, Q3 2026
    calc:     SUM of 8 cells (I21 ... I28) = 16,697
    hint:     The stated figure is the number of households (FA-1: I9 + I10 + I11 + I12 = 3,513), not people. Households and individuals mixed up?

INCONSISTENT  '1,896'  workbook: 79
    sentence: From WH-03, the Tripoli centre received 1,896 boxes of canned cheese for families with young children, ...
    read as:  dispatch sheet, Canned cheese 200 g (FOO-CHE-002), dispatched, destination Tripoli centre, warehouse WH-03 Tripoli, Q3 2026, in boxes
    calc:     I48 + I61 + I74 = 1,896 pieces / 24 per box = 79 boxes
    hint:     The stated figure is the number of pieces (1,896). In boxes of 24 it is 79. Pieces written as boxes?

INCONSISTENT  '468'  workbook: 528
    sentence: The warehouse received 1,200 bottles, dispatched 792 and closed the quarter with a balance of 468 bottles.
    read as:  stock sheet, Sunflower oil 1 L (FOO-OIL-001), closing, warehouse WH-03 Tripoli, Q3 2026, in pieces
    calc:     J25 = 528 pieces
    note:     Stock arithmetic in the text: opening 120 + received 1,200 - dispatched 792 = 528, but the stated balance is 468.
...
review page written to review.html
```

`review.html` is one self-contained file (no external scripts or fonts) that can be shared with the report.
The exit code is 1 when any figure is inconsistent, 0 when none is, 2 when a file cannot be read, so the
command can gate a folder of reports in CI. The same page runs as a small web app with a sample picker and
an upload form: `numcheck serve`, then open http://127.0.0.1:8110.

## How it works

There is no language model and no API key anywhere. Every result comes from fixed rules, so the same
report always gives the same answer and every answer can be traced to a rule and a cell.

| Step | What happens |
|---|---|
| Read | `.docx` paragraphs, headings and **tables** (each table row is read with its column headers), or Markdown. The `.xlsx` workbook is read sheet by sheet: an indicator table (target, achieved, by district or shelter, sex, age group, period), a dispatch summary (item, pieces per box, warehouse, destination, month, pieces) and a stock sheet (opening, received from purchases and in kind, dispatched, closing). Column names are matched loosely. |
| Extract | Every number: `3,284`, `62%`, `1.2 thousand`, `forty-two`, `about a third of`, `36 boxes and 17 pieces`, with any hedge (`nearly`, `over`, `about`). Dates, years, section and page references, phone numbers, codes such as `WH-03`, durations and ages are skipped. |
| Interpret | From the words around the number. Indicator figures: which indicator, district or shelter, period (`last quarter`, `since April`, `at the end of June` is Q2), sex and age group. Stock figures: which item, warehouse, destination, month, and whether received, dispatched, opening or closing, in pieces or boxes. |
| Look up | Sum the matching cells; boxes are pieces divided by the item's pieces per box. |
| Compare | With the rounding implied by how the figure is written and the hedge window from the config (`nearly 3,000` allows 2,850 to 3,000). |
| Explain | Where the stated figure is found elsewhere: the pieces figure quoted as boxes or the reverse, the household figure quoted as people, last quarter's value, two swapped digits. Arithmetic inside the text: women plus men, districts against the total, opening plus received minus dispatched against the balance. |

All vocabulary lives in [numcheck/config/matching.toml](numcheck/config/matching.toml): units, synonyms,
place aliases, age words, the words that send a figure to the stock sheets, hedge tolerances.

**The weak-match rule.** A false "consistent" is the worst error this tool can make, so a figure is only
checked when the match is clear: the indicator must score at least 1.0 on keywords and beat the runner-up;
the item, warehouse and destination must each be unambiguous. Otherwise the figure is reported as
**unverifiable**, with the reason.

## The data

[scripts/generate_data.py](scripts/generate_data.py) writes three synthetic quarterly reports from "the
Organization", each four pages in Word (measured in Word) with one table, its three-sheet workbook and a
gold file that labels every number in the text. All projects, warehouses (`WH-03`...), partners, shelters,
item codes and figures are invented; the place names are Lebanese geography only.

| Report | Use | Figures in gold | Planted errors |
|---|---|---|---|
| `FA-2026` food assistance: parcels and food items from four warehouses to centres and partners | tuning | 44 | 7 |
| `EA-2026` emergency appeal: mattresses, blankets and hygiene kits to collective shelters, in-kind stock | tuning | 47 | 7 |
| `WASH-2026` hygiene and winterisation in Baalbek, Hermel and Zahle | **held out** | 43 | 7 |

Planted errors: pieces quoted as boxes and boxes quoted as pieces; a stock balance that is not opening plus
received minus dispatched; the household figure quoted as people; a total across districts or a table row
that does not add up; a women/men split that does not sum; a figure left from the previous quarter; two
swapped digits; a hedge that overstates.

How the held-out report was kept unseen: I wrote its text, workbook and gold labels first and committed
them (`76c7398`) before changing any rule for this scenario. While tuning, `scripts/benchmark.py` skips it
unless `--final` is given. I ran it once, after the rules were frozen at commit `3137a11`, and changed no
rule afterwards. (I later removed unused entries from the config and reran it only to confirm the output
was byte-for-byte the same.) Because I wrote its text, it is less independent than a report written by
someone else.

## Results

`python scripts/benchmark.py --final` (full output in [docs/benchmark-output.txt](docs/benchmark-output.txt)):

```
== ALL HELDOUT REPORTS ==
  claims in gold                        43  (consistent 30, planted errors 7, not in workbook 6)
  planted errors caught                 6/7 (86%)
  wrong figures passed as consistent    0 planted errors, 0 claims with no workbook support
  false alarms                          2 of 30 correct figures; 0 of 6 figures not in the workbook
  correct figures confirmed             26/30 (87%)
  correct figures left unverifiable     2
  claims matched to the right cell(s)   32/37 (86%) of checkable claims (32/34 of those the tool attempted)
  figures not extracted                 0
  non-claims ignored                    16/17 (94%)
  numbers extracted that are not in gold 2
```

The two tuning reports score 100% on every line, which says little because the rules were adjusted on
them. Next to the first version of this project (a different, three-country scenario with only an
indicator table; its numbers are void now that the data has changed, and are shown only for comparison):

| Held-out report | First version | This version |
|---|---|---|
| Planted errors caught | 5 of 6 | 6 of 7 |
| Wrong figures passed as consistent | 0 | 0 |
| False alarms on correct figures | 1 of 20 | 2 of 30 |
| Correct figures confirmed | 11 of 20 | 26 of 30 |
| Matched to the right cell(s) | 15 of 26 | 32 of 37 |
| Non-claims ignored | 21 of 24 | 16 of 17 |

The 2 "numbers extracted that are not in gold" are mine, not the tool's: the held-out text says "the three
districts" twice and I did not label those words; the tool reported both as unverifiable.

## Where it fails

Real sentences from the held-out `WASH-2026` report:

- *"The warehouse received 1,940 kits and dispatched 1,832, leaving a balance of 308 kits on 30
  September."* The previous sentence says "family hygiene kits", but this one only says "kits", and the
  project also stocks child winter clothing kits. All three figures were left unverifiable, so the planted
  wrong balance (the workbook says 188) was missed. Unverifiable, not wrongly consistent, but a miss.
- *"Child winter clothing kits for Hermel were dispatched as 40 boxes and 1 piece..."* "For Hermel" names
  the district, not the destination "Hermel centre", so the checker summed every destination of that item
  (521 pieces against 321) and raised a false alarm.
- *"The thermal blanket balance in the same warehouse was 760 pieces..."* "The same warehouse" points two
  sentences back, past the unverifiable sentence above. The checker added both warehouses (1,760) and
  raised a false alarm.
- *"Children under 18 made up the largest group with 4,869 people..."* The age limit "18" was taken as a
  figure (reported as unverifiable).

## What I would add next

- Follow "the same warehouse" and "these kits" across more than one sentence, and read a district name
  as its centre when the dispatch sheet has exactly one centre in that district.
- Read the stock card (every receipt and waybill) instead of quarterly totals, to check figures by date
  and by expiry.
- Run the check from a Google Sheets menu or an n8n job when a report is saved, and post the review page
  link to the team.
- An LLM could suggest the match for figures the rules leave unverifiable, shown as a suggestion; the
  rules would still decide what counts as consistent.

## Layout

```
numcheck/            numbers.py (extract), matcher.py (indicator figures), stock.py (dispatch and stock
                     figures), checks.py (look up and compare), workbook.py, narrative.py (incl. tables),
                     render.py + static/review.html (page), cli.py, app.py
numcheck/config/     matching.toml: vocabulary, tolerances, weak-match thresholds
scripts/             generate_data.py, datagen/ (engine and the three report templates), benchmark.py
data/                three synthetic reports: report.docx, report.md, indicators.xlsx, gold.json
tests/               pytest: number forms, hedges, non-claims, derived checks, weak-match rule,
                     boxes and pieces, stock arithmetic, households vs people, Word tables, CLI, app
```

Run the tests with `pip install -e ".[dev]"` then `pytest`.

## Licence

MIT, see [LICENSE](LICENSE). All reports, workbooks and figures in this repository are synthetic.

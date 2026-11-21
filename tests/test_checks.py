"""End-to-end checks against a small workbook (see conftest.BASIC_ROWS).

Q3 2026 is the current period. Households HH-1: North 800 (H6), South 1,150 (H7), total 1,950;
targets 1,000 (G6) and 1,200 (G7). Q2 total 1,850. People PP-1 Q3: women 1,100 + 520 = 1,620,
men 900 + 480 = 1,380, total 3,000.
"""
from conftest import by_text, write_workbook


def refs(r):
    return sorted(c["ref"] for c in r.cells)


# ---------------------------------------------------------------- direct figures

def test_direct_figure_consistent_with_cells(run):
    rep = run("The Organization delivered food parcels to 1,950 households this quarter.")
    r = by_text(rep, "1,950")
    assert r.status == "consistent"
    assert refs(r) == ["Indicators!H6", "Indicators!H7"]
    assert r.calculation == "H6 + H7 = 1,950"


def test_direct_figure_inconsistent_shows_expected_and_cells(run):
    rep = run("The Organization delivered food parcels to 1,905 households this quarter.")
    r = by_text(rep, "1,905")
    assert r.status == "inconsistent"
    assert r.expected == 1950
    assert refs(r) == ["Indicators!H6", "Indicators!H7"]
    assert any("swapped" in h for h in r.hints)


def test_location_figure(run):
    rep = run("In the South, food parcels reached 1,150 households.")
    r = by_text(rep, "1,150")
    assert r.status == "consistent"
    assert r.interp.locations == ["South"]
    assert refs(r) == ["Indicators!H7"]


def test_previous_quarter_figure_is_flagged_with_a_hint(run):
    rep = run("Food parcels reached 1,850 households this quarter.")
    r = by_text(rep, "1,850")
    assert r.status == "inconsistent"
    assert any("Q2 2026" in h for h in r.hints)


def test_figure_for_last_quarter_is_read_as_last_quarter(run):
    rep = run("Food parcels reached 1,950 households, up from 1,850 last quarter.")
    assert by_text(rep, "1,950").status == "consistent"
    r = by_text(rep, "1,850")
    assert r.status == "consistent" and r.interp.periods == ["Q2 2026"]


def test_hedged_figure_within_tolerance(run):
    rep = run("Food parcels reached nearly 2,000 households.")
    assert by_text(rep, "nearly 2,000").status == "consistent"


def test_hedge_that_overstates_is_inconsistent(run):
    rep = run("Food parcels reached more than 2,000 households.")
    r = by_text(rep, "more than 2,000")
    assert r.status == "inconsistent"
    assert any("overstates" in h for h in r.hints)


# ---------------------------------------------------------------- derived figures

def test_women_plus_men_equals_total(run):
    rep = run("Hygiene promotion reached 3,000 people: 1,620 women and girls and 1,380 men and boys.")
    total = by_text(rep, "3,000")
    assert total.status == "consistent"
    assert refs(total) == ["Indicators!H10", "Indicators!H11", "Indicators!H8", "Indicators!H9"]
    assert by_text(rep, "1,620").status == "consistent"
    assert by_text(rep, "1,380").status == "consistent"
    assert any("as stated" in n for n in total.notes)


def test_women_men_split_that_does_not_sum(run):
    rep = run("Hygiene promotion reached 3,000 people: 1,620 women and girls and 1,280 men and boys.")
    men = by_text(rep, "1,280")
    assert men.status == "inconsistent" and men.expected == 1380
    assert any("1,620 + 1,280 = 2,900" in n for n in men.notes)


def test_percent_of_target_is_achieved_over_target(run):
    # 1,950 / 2,200 = 88.6%
    rep = run("Food parcels reached 1,950 households, 89 percent of the quarterly target.")
    r = by_text(rep, "89 percent")
    assert r.status == "consistent"
    assert r.interp.measure == "pct_target"
    assert refs(r) == ["Indicators!G6", "Indicators!G7", "Indicators!H6", "Indicators!H7"]


def test_percent_against_the_wrong_target(run):
    # 1,950 / 2,000 (the Q2 target) = 97.5%
    rep = run("Food parcels reached 1,950 households, 98 percent of the quarterly target.")
    r = by_text(rep, "98 percent")
    assert r.status == "inconsistent"
    assert any("Q2 2026 target" in h for h in r.hints)


def test_share_of_women(run):
    # 1,620 / 3,000 = 54%
    rep = run("Hygiene promotion reached 3,000 people. Women and girls made up 54 percent of the people reached.")
    r = by_text(rep, "54 percent")
    assert r.status == "consistent" and r.interp.measure == "share"


def test_sum_across_locations(run):
    rep = run("Food parcels reached 1,950 households: 800 in the North and 1,150 in the South.")
    total = by_text(rep, "1,950")
    assert total.status == "consistent" and total.interp.locations is None
    assert by_text(rep, "800").interp.locations == ["North"]
    assert by_text(rep, "1,150").interp.locations == ["South"]
    assert any("800 + 1,150 = 1,950" in n for n in total.notes)


def test_locations_that_do_not_add_up(run):
    rep = run("Food parcels reached 1,950 households: 800 in the North and 1,105 in the South.")
    south = by_text(rep, "1,105")
    assert south.status == "inconsistent"
    assert any("gap of 45" in n for n in south.notes)


# ---------------------------------------------------------------- weak-match rule

def test_number_counting_something_else_is_unverifiable(run):
    rep = run("The team visited 36 shops that accept the card.")
    assert by_text(rep, "36").status == "unverifiable"


def test_unit_without_any_indicator_keyword_is_unverifiable(run):
    rep = run("Floods damaged 800 households in the North.")
    r = by_text(rep, "800")
    # 800 is exactly the North value in the workbook, but nothing in the sentence says the
    # floods are about food parcels. A coincidence must not be reported as consistent.
    assert r.status == "unverifiable"
    assert "weak match" in r.reason


def test_two_equally_good_indicators_is_unverifiable(tmp_path, run):
    wb = write_workbook(tmp_path / "two.xlsx", [
        ("A", "Households receiving cash", "Households", "Q3 2026", "North", "All", 10, 10),
        ("B", "Households receiving vouchers", "Households", "Q3 2026", "North", "All", 10, 12),
    ])
    rep = run("The project assisted 10 households receiving support.", wb)
    r = by_text(rep, "10")
    assert r.status == "unverifiable" and "ambiguous" in r.reason


def test_plans_are_unverifiable(run):
    rep = run("Next quarter the project plans to reach 2,500 households with food parcels.")
    assert by_text(rep, "2,500").status == "unverifiable"


def test_subset_cues_are_unverifiable(run):
    rep = run("Card failures affected 150 households receiving food parcels in the North.")
    assert by_text(rep, "150").status == "unverifiable"


def test_sex_breakdown_missing_in_workbook_is_unverifiable(run):
    rep = run("Food parcels reached 1,950 households, 900 of them women.")
    assert by_text(rep, "900").status == "unverifiable"


def test_location_not_in_workbook_is_not_matched_to_a_total(run):
    rep = run("In the North and the South, food parcels reached 1,950 households.")
    assert by_text(rep, "1,950").status == "consistent"


def test_percentage_with_no_rate_indicator_is_unverifiable(run):
    rep = run("Prices rose by 9 percent between June and September.")
    assert by_text(rep, "9 percent").status == "unverifiable"


# ---------------------------------------------------------------- workbook layouts

def test_other_column_names_and_percent_format(tmp_path, run):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Matrix"
    for c, h in enumerate(("Code", "Indicator description", "Unit of measure", "Reporting period",
                           "Department", "Gender", "Planned", "Actual"), start=1):
        ws.cell(row=1, column=c, value=h)
    rows = [("E1", "Children attending school sessions", "%", "Q3 2026", "Total", "Total", 0.75, 0.66)]
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            if c >= 7:
                cell.number_format = "0%"
    path = tmp_path / "matrix.xlsx"
    wb.save(path)
    rep = run("School attendance: 66 percent of children attended sessions.", path)
    r = by_text(rep, "66 percent")
    assert r.status == "consistent" and refs(r) == ["Matrix!H2"]


# ---------------------------------------------------------------- the generated reports

def test_tuning_reports_pass_no_wrong_figure_as_consistent():
    """Regression guard on the two tuning reports (never the held-out one)."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from benchmark import evaluate
    for name in ("fa-2026-q3", "ea-2026-q3"):
        m = evaluate(root / "data" / name, verbose=False)
        assert m["planted_passed_consistent"] == 0
        assert m["unsupported_passed_consistent"] == 0
        assert m["caught"] == m["planted"]

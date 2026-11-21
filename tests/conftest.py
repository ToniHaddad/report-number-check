from pathlib import Path

import pytest
from openpyxl import Workbook

from numcheck.config import load_config

HEADERS = ("Indicator ID", "Indicator", "Unit", "Period", "Location", "Sex", "Target", "Achieved")


@pytest.fixture
def cfg():
    return load_config()


def write_workbook(path: Path, rows, headers=HEADERS):
    wb = Workbook()
    ws = wb.active
    ws.title = "Indicators"
    ws["A1"] = "Test indicator table"
    for c, h in enumerate(headers, start=1):
        ws.cell(row=3, column=c, value=h)
    for r, row in enumerate(rows, start=4):
        for c, v in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=v)
    wb.save(path)
    return path


# A small workbook used by most end-to-end tests. Data rows start at Excel row 4.
BASIC_ROWS = [
    # households, by location, two quarters
    ("HH-1", "Households receiving food parcels", "Households", "Q2 2026", "North", "All", 900, 850),   # 4
    ("HH-1", "Households receiving food parcels", "Households", "Q2 2026", "South", "All", 1100, 1000),  # 5
    ("HH-1", "Households receiving food parcels", "Households", "Q3 2026", "North", "All", 1000, 800),   # 6
    ("HH-1", "Households receiving food parcels", "Households", "Q3 2026", "South", "All", 1200, 1150),  # 7
    # people, by location and sex, current quarter
    ("PP-1", "People reached by hygiene promotion", "People", "Q3 2026", "North", "Female", 1000, 1100),   # 8
    ("PP-1", "People reached by hygiene promotion", "People", "Q3 2026", "North", "Male", 1000, 900),      # 9
    ("PP-1", "People reached by hygiene promotion", "People", "Q3 2026", "South", "Female", 500, 520),     # 10
    ("PP-1", "People reached by hygiene promotion", "People", "Q3 2026", "South", "Male", 500, 480),       # 11
    # a second indicator counting households, to test ambiguity
    ("HH-2", "Households trained in financial literacy", "Households", "Q3 2026", "North", "All", 300, 250),  # 12
    ("HH-2", "Households trained in financial literacy", "Households", "Q3 2026", "South", "All", 300, 290),  # 13
]


@pytest.fixture
def basic_wb(tmp_path):
    return write_workbook(tmp_path / "indicators.xlsx", BASIC_ROWS)


@pytest.fixture
def run(tmp_path, basic_wb):
    """Check a markdown narrative against the basic workbook; returns the results."""
    from numcheck.pipeline import check

    def _run(md: str, wb=None):
        p = tmp_path / "report.md"
        p.write_text(md, encoding="utf-8")
        return check(p, wb or basic_wb)
    return _run


def by_text(rep, text):
    hits = [r for r in rep.results if r.claim.text == text]
    assert hits, f"{text!r} not found in {[r.claim.text for r in rep.results]}"
    return hits[0]

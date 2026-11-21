"""Stock and dispatch figures, Word tables, age groups and month names.

The workbook built here has an indicator table, a dispatch summary and a stock sheet.
Canned cheese comes 24 pieces to a box. Q3 2026 is the current period.
"""
from openpyxl import Workbook

from conftest import by_text

IND = ("Indicator ID", "Indicator", "Unit", "Period", "District", "Sex", "Age group", "Target", "Achieved")
DSP = ("Period", "Month", "Item code", "Item", "Pieces per box", "Warehouse", "Destination", "Destination type",
       "Pieces dispatched")
STK = ("Period", "Warehouse", "Item code", "Item", "Pieces per box", "Opening balance", "Received (purchase)",
       "Received (in-kind)", "Dispatched", "Closing balance")


def _sheet(wb, title, headers, rows, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=v)


def stock_workbook(path):
    wb = Workbook()
    _sheet(wb, "Indicators", IND, [
        ("H-1", "Households receiving food parcels", "Households", "Q2 2026", "Tripoli", "All", "All", 900, 850),  # 2
        ("H-1", "Households receiving food parcels", "Households", "Q3 2026", "Tripoli", "All", "All", 1000, 960),  # 3
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Female",
         "Children (0-17)", 1000, 900),                                                                          # 4
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Female",
         "Adults (18-59)", 1000, 1100),                                                                          # 5
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Female",
         "Older people (60+)", 200, 180),                                                                        # 6
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Male",
         "Children (0-17)", 1000, 880),                                                                          # 7
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Male",
         "Adults (18-59)", 1000, 1000),                                                                          # 8
        ("P-1", "Individuals in households receiving food parcels", "People", "Q3 2026", "Tripoli", "Male",
         "Older people (60+)", 200, 140),                                                                        # 9
    ], first=True)
    _sheet(wb, "Dispatch summary", DSP, [
        ("Q3 2026", "Jul 2026", "FOO-CHE-002", "Canned cheese 200 g", 24, "WH-03 Tripoli", "Tripoli centre", "Centre", 480),  # 2
        ("Q3 2026", "Aug 2026", "FOO-CHE-002", "Canned cheese 200 g", 24, "WH-03 Tripoli", "Tripoli centre", "Centre", 720),  # 3
        ("Q3 2026", "Aug 2026", "FOO-CHE-002", "Canned cheese 200 g", 24, "WH-03 Tripoli", "Cedar Hands Association",
         "Partner", 245),                                                                                                     # 4
        ("Q2 2026", "May 2026", "FOO-CHE-002", "Canned cheese 200 g", 24, "WH-03 Tripoli", "Tripoli centre", "Centre", 960),  # 5
    ])
    _sheet(wb, "Stock", STK, [
        ("Q3 2026", "WH-03 Tripoli", "FOO-CHE-002", "Canned cheese 200 g", 24, 100, 1200, 240, 1445, 95),
    ])
    wb.save(path)
    return path


def run_stock(run, tmp_path, md):
    return run(md, stock_workbook(tmp_path / "stock.xlsx"))


def test_dispatch_in_pieces_to_a_destination(run, tmp_path):
    rep = run_stock(run, tmp_path, "From WH-03, the Tripoli centre received 1,200 pieces of canned cheese this quarter.")
    r = by_text(rep, "1,200")
    assert r.status == "consistent"
    assert r.interp.source == "dispatch"
    assert sorted(c["ref"] for c in r.cells) == ["Dispatch summary!I2", "Dispatch summary!I3"]


def test_dispatch_in_boxes_uses_pieces_per_box(run, tmp_path):
    rep = run_stock(run, tmp_path, "The Tripoli centre received 50 boxes of canned cheese from WH-03.")
    r = by_text(rep, "50")
    assert r.status == "consistent" and r.interp.unit == "boxes"
    assert "/ 24 per box = 50 boxes" in r.calculation


def test_pieces_written_as_boxes(run, tmp_path):
    rep = run_stock(run, tmp_path, "The Tripoli centre received 1,200 boxes of canned cheese from WH-03.")
    r = by_text(rep, "1,200")
    assert r.status == "inconsistent"
    assert any("Pieces written as boxes" in h for h in r.hints)


def test_boxes_written_as_pieces(run, tmp_path):
    rep = run_stock(run, tmp_path, "The Tripoli centre received 50 pieces of canned cheese from WH-03.")
    r = by_text(rep, "50")
    assert r.status == "inconsistent"
    assert any("Boxes written as pieces" in h for h in r.hints)


def test_boxes_and_pieces_together(run, tmp_path):
    # 245 pieces = 10 boxes of 24 and 5 pieces
    rep = run_stock(run, tmp_path, "The Cedar Hands Association received 10 boxes and 5 pieces of canned cheese.")
    r = by_text(rep, "10 boxes and 5 pieces")
    assert r.status == "consistent"


def test_month_filter_on_dispatches(run, tmp_path):
    rep = run_stock(run, tmp_path, "Canned cheese dispatches peaked in August, when 965 pieces left the warehouse.")
    r = by_text(rep, "965")
    assert r.status == "consistent" and r.interp.months == ["august"]


def test_stock_balance_and_arithmetic(run, tmp_path):
    md = ("At WH-03 Tripoli the quarter opened with 100 pieces of canned cheese. The warehouse received "
          "1,440 pieces, dispatched 1,445 and closed the quarter with a balance of 125 pieces.")
    rep = run_stock(run, tmp_path, md)
    assert by_text(rep, "100").status == "consistent"
    assert by_text(rep, "1,440").status == "consistent"        # 1,200 purchased + 240 in kind
    assert by_text(rep, "1,445").status == "consistent"
    bal = by_text(rep, "125")
    assert bal.status == "inconsistent" and bal.expected == 95
    assert any("100 + received 1,440 - dispatched 1,445 = 95" in n for n in bal.notes)


def test_in_kind_receipts(run, tmp_path):
    rep = run_stock(run, tmp_path, "A local shop donated 240 pieces of canned cheese in kind to WH-03.")
    r = by_text(rep, "240")
    assert r.status == "consistent" and r.interp.measure == "received_inkind"


def test_households_quoted_as_people(run, tmp_path):
    rep = run_stock(run, tmp_path, "In Tripoli the food parcels reached 960 people this quarter.")
    r = by_text(rep, "960")
    assert r.status == "inconsistent" and r.expected == 4200
    assert any("number of households" in h for h in r.hints)


def test_month_name_maps_to_its_quarter(run, tmp_path):
    rep = run_stock(run, tmp_path, "At the end of June, 850 households in Tripoli were receiving food parcels.")
    r = by_text(rep, "850")
    assert r.status == "consistent" and r.interp.periods == ["Q2 2026"]


def test_age_group(run, tmp_path):
    rep = run_stock(run, tmp_path, "The parcels reached 320 older people in Tripoli receiving food parcels.")
    r = by_text(rep, "320")
    assert r.status == "consistent" and r.interp.age == "older"


def test_numbers_inside_a_word_table(tmp_path):
    from docx import Document

    from numcheck.pipeline import check
    doc = Document()
    doc.add_paragraph("Table 1 shows the dispatches of the quarter.")
    t = doc.add_table(rows=2, cols=4)
    for i, h in enumerate(["Destination", "Item", "Pieces dispatched", "Boxes"]):
        t.rows[0].cells[i].text = h
    for i, v in enumerate(["Tripoli centre", "Canned cheese", "1,200", "50"]):
        t.rows[1].cells[i].text = v
    path = tmp_path / "report.docx"
    doc.save(path)
    rep = check(path, stock_workbook(tmp_path / "stock.xlsx"))
    pcs, box = by_text(rep, "1,200"), by_text(rep, "50")
    assert pcs.status == "consistent" and box.status == "consistent"
    assert box.interp.unit == "boxes"
    assert rep.blocks[1].kind == "row" and rep.blocks[1].text.startswith("Destination: Tripoli centre")

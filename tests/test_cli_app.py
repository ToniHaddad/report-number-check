from pathlib import Path

from fastapi.testclient import TestClient

from numcheck.app import app
from numcheck.cli import main

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "fa-2026-q3"


def test_cli_exit_code_1_when_inconsistent(tmp_path, capsys):
    out = tmp_path / "review.html"
    code = main(["check", str(SAMPLE / "report.docx"), str(SAMPLE / "indicators.xlsx"), "--out", str(out)])
    assert code == 1
    page = out.read_text(encoding="utf-8")
    assert "<script" in page and "Number check" in page
    assert "http" not in page.split("<body>")[1].split("<script")[0]  # no external resources
    assert "INCONSISTENT" in capsys.readouterr().out


def test_cli_exit_code_0_when_clean(tmp_path, basic_wb):
    md = tmp_path / "ok.md"
    md.write_text("# Report\n\nNorthbridge Relief delivered cash assistance to 1,950 households.\n", encoding="utf-8")
    assert main(["check", str(md), str(basic_wb), "-q"]) == 0


def test_cli_exit_code_2_on_bad_input(tmp_path, basic_wb):
    bad = tmp_path / "report.pdf"
    bad.write_text("x")
    assert main(["check", str(bad), str(basic_wb)]) == 2


def test_app_serves_sample_and_upload():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200 and "Number check" in r.text and "Check another report" in r.text
    with open(SAMPLE / "report.docx", "rb") as n, open(SAMPLE / "indicators.xlsx", "rb") as w:
        r = client.post("/check", files={"narrative": ("report.docx", n), "workbook": ("indicators.xlsx", w)})
    assert r.status_code == 200 and 'class="claim s-inconsistent"' in r.text
    r = client.get("/api/sample/fa-2026-q3")
    assert r.json()["counts"]["inconsistent"] == 7


def test_markdown_narrative_reads_like_docx():
    from numcheck.narrative import read_narrative
    a = [b.text for b in read_narrative(SAMPLE / "report.docx")]
    b = [b.text for b in read_narrative(SAMPLE / "report.md")]
    assert a == b

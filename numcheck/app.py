"""One-page web app: the review page, with a form to pick a sample or upload a report.

    numcheck serve            # http://127.0.0.1:8110
"""
from __future__ import annotations

import html
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .cli import _json
from .pipeline import check
from .render import render_html

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SAMPLE = "lebanon-cash-q3-2026"

app = FastAPI(title="numcheck", docs_url=None, redoc_url=None)


def samples() -> list[str]:
    if not DATA.is_dir():
        return []
    return sorted(d.name for d in DATA.iterdir() if (d / "report.docx").exists() and (d / "indicators.xlsx").exists())


def toolbar(current: str | None) -> str:
    opts = "".join(f'<option value="{s}"{" selected" if s == current else ""}>{html.escape(s)}</option>'
                   for s in samples())
    sample_form = (f'<form method="get" action="/sample" style="display:grid;gap:8px">'
                   f'<label>Synthetic sample report<select name="name">{opts}</select></label>'
                   f'<button class="btn" type="submit">Open sample</button></form><hr>') if opts else ""
    return (
        '<details class="upload"><summary class="icon-btn">Check another report</summary>'
        f'<div class="upload-form">{sample_form}'
        '<form method="post" action="/check" enctype="multipart/form-data" style="display:grid;gap:8px">'
        '<label>Narrative report (.docx or .md)<input type="file" name="narrative" accept=".docx,.md" required></label>'
        '<label>Indicator workbook (.xlsx)<input type="file" name="workbook" accept=".xlsx" required></label>'
        '<button class="btn" type="submit">Check figures</button>'
        '<span style="font-size:12px;color:var(--muted)">Files are checked on this machine and deleted afterwards.</span>'
        '</form></div></details>')


def _sample_paths(name: str) -> tuple[Path, Path]:
    if name not in samples():
        raise HTTPException(404, f"no sample called {name!r}")
    d = DATA / name
    return d / "report.docx", d / "indicators.xlsx"


@app.get("/", response_class=HTMLResponse)
def index():
    if DEFAULT_SAMPLE in samples():
        return sample(DEFAULT_SAMPLE)
    return HTMLResponse("<p>No sample data found. POST a report to /check.</p>")


@app.get("/sample", response_class=HTMLResponse)
def sample_query(name: str):
    return RedirectResponse(f"/sample/{name}", status_code=303)


@app.get("/sample/{name}", response_class=HTMLResponse)
def sample(name: str):
    narrative, workbook = _sample_paths(name)
    return HTMLResponse(render_html(check(narrative, workbook), toolbar(name)))


@app.get("/api/sample/{name}")
def sample_json(name: str):
    narrative, workbook = _sample_paths(name)
    return JSONResponse(_json(check(narrative, workbook)))


@app.post("/check", response_class=HTMLResponse)
async def check_upload(narrative: UploadFile = File(...), workbook: UploadFile = File(...)):
    nsuf = Path(narrative.filename or "").suffix.lower()
    wsuf = Path(workbook.filename or "").suffix.lower()
    if nsuf not in (".docx", ".md") or wsuf != ".xlsx":
        raise HTTPException(400, "send a .docx or .md narrative and an .xlsx workbook")
    tmp = Path(tempfile.mkdtemp(prefix="numcheck-"))
    try:
        npath = tmp / Path(narrative.filename).name
        wpath = tmp / Path(workbook.filename).name
        with npath.open("wb") as f:
            shutil.copyfileobj(narrative.file, f)
        with wpath.open("wb") as f:
            shutil.copyfileobj(workbook.file, f)
        try:
            rep = check(npath, wpath)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return HTMLResponse(render_html(rep, toolbar(None)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/healthz")
def healthz():
    return {"ok": True}

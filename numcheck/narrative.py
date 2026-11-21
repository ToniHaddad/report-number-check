"""Read a narrative report (.docx or .md) into a list of blocks.

Paragraphs and headings become one block each. A table becomes one block per data row, with
text "Header: cell | Header: cell", so that the words of the column header sit next to each number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    index: int
    kind: str          # "heading", "paragraph" or "row" (a table row)
    level: int         # 0 = title, 1, 2, ... for headings; 0 otherwise
    text: str
    heading: str = ""  # text of the nearest heading above
    table: int | None = None                       # table number, for rows
    headers: list[str] = field(default_factory=list)
    cells: list[tuple[int, int]] = field(default_factory=list)   # (start, end) of each cell value in text


def row_text(headers: list[str], values: list[str]) -> tuple[str, list[tuple[int, int]]]:
    text, spans = "", []
    for i, (h, v) in enumerate(zip(headers, values)):
        if i:
            text += " | "
        text += f"{h}: "
        spans.append((len(text), len(text) + len(v)))
        text += v
    return text, spans


def read_narrative(path: str | Path) -> list[Block]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        raw = _read_docx(path)
    elif suffix in (".md", ".markdown", ".txt"):
        raw = _read_md(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"unsupported narrative format: {suffix} (use .docx or .md)")
    return _number(raw)


def _clean(s: str) -> str:
    return " ".join(s.split())


def _read_docx(path: Path) -> list[tuple]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    out = []
    for el in doc.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, doc)
            text = _clean(p.text)
            if not text:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style == "title":
                out.append(("heading", 0, text))
            elif style.startswith("heading"):
                m = re.search(r"(\d+)", style)
                out.append(("heading", int(m.group(1)) if m else 1, text))
            else:
                out.append(("paragraph", 0, text))
        elif tag == "tbl":
            rows = [[_clean(c.text) for c in r.cells] for r in Table(el, doc).rows]
            if rows:
                out.append(("table", rows[0], rows[1:]))
    return out


_EMPH = re.compile(r"(\*\*|__|\*|_)(.+?)\1")


def _read_md(text: str) -> list[tuple]:
    out, buf, table = [], [], []

    def flush():
        if buf:
            out.append(("paragraph", 0, _EMPH.sub(r"\2", " ".join(buf))))
            buf.clear()

    def flush_table():
        rows = [r for r in table if not re.fullmatch(r"\|?[\s:|-]+\|?", r)]
        if rows:
            cells = [[_clean(c) for c in r.strip().strip("|").split("|")] for r in rows]
            out.append(("table", cells[0], cells[1:]))
        table.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            flush()
            table.append(s)
            continue
        if table:
            flush_table()
        if not s:
            flush()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            out.append(("heading", len(m.group(1)) - 1, _EMPH.sub(r"\2", m.group(2).strip())))
            continue
        if re.match(r"^([-*+]|\d+\.)\s+", s) and not re.match(r"^\d+\.\d", s):
            flush()
            buf.append(re.sub(r"^([-*+]|\d+\.)\s+", "", s))
            flush()
            continue
        buf.append(s)
    if table:
        flush_table()
    flush()
    return out


def _number(raw) -> list[Block]:
    blocks, heading, tables = [], "", 0
    for item in raw:
        if item[0] == "table":
            _, headers, rows = item
            tables += 1
            for values in rows:
                text, spans = row_text(headers, values)
                blocks.append(Block(len(blocks), "row", 0, text, heading, tables, list(headers), spans))
            continue
        kind, level, text = item
        blocks.append(Block(len(blocks), kind, level, text, heading))
        if kind == "heading" and level > 0:
            heading = text
    return blocks

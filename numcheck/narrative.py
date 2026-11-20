"""Read a narrative report (.docx or .md) into a list of blocks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Block:
    index: int
    kind: str          # "heading" or "paragraph"
    level: int         # 0 = title, 1, 2, ... for headings; 0 for paragraphs
    text: str
    heading: str = ""  # text of the nearest heading above (for paragraphs)


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


def _read_docx(path: Path) -> list[tuple[str, int, str]]:
    from docx import Document

    out = []
    for p in Document(str(path)).paragraphs:
        text = " ".join(p.text.split())
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
    return out


_EMPH = re.compile(r"(\*\*|__|\*|_)(.+?)\1")


def _read_md(text: str) -> list[tuple[str, int, str]]:
    out, buf = [], []

    def flush():
        if buf:
            out.append(("paragraph", 0, _EMPH.sub(r"\2", " ".join(buf))))
            buf.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s:
            flush()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            level = len(m.group(1)) - 1
            out.append(("heading", level, _EMPH.sub(r"\2", m.group(2).strip())))
            continue
        if re.match(r"^([-*+]|\d+\.)\s+", s) and not re.match(r"^\d+\.\d", s):
            flush()
            buf.append(re.sub(r"^([-*+]|\d+\.)\s+", "", s))
            flush()
            continue
        buf.append(s)
    flush()
    return out


def _number(raw) -> list[Block]:
    blocks, heading = [], ""
    for i, (kind, level, text) in enumerate(raw):
        blocks.append(Block(i, kind, level, text, heading))
        if kind == "heading" and level > 0:
            heading = text
    return blocks

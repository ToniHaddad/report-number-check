"""Tokens, stems, sentences and clauses. Plain regular expressions, no NLP model."""
from __future__ import annotations

import re
from dataclasses import dataclass

WORD = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]*|\d[\d,]*(?:\.\d+)?|%|\$")

STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "from", "by", "and", "or", "through",
    "their", "they", "them", "can", "who", "that", "this", "these", "those", "per", "within", "as", "be",
    "is", "are", "were", "was", "been", "has", "have", "had", "it", "its", "total", "number", "report",
    "reporting", "reported", "quarter", "least", "up", "set", "into", "out", "s", "all", "than", "more",
    "new", "which", "who", "whom", "also", "now", "only", "each", "every",
}

ABBREVIATIONS = {"p", "pp", "e.g", "i.e", "no", "approx", "st", "dr", "mr", "mrs", "ms", "vs", "etc", "fig", "ref"}


def stem(word: str) -> str:
    """A deliberately small stemmer: enough to make 'trained' meet 'training'."""
    w = word.lower().strip("'’.-")
    w = w.replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suf in ("ing", "ion", "ed", "ance", "ence"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    if len(w) > 4 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    return w


@dataclass
class Token:
    text: str
    start: int
    end: int

    @property
    def low(self) -> str:
        return self.text.lower()


def tokens(text: str, offset: int = 0) -> list[Token]:
    return [Token(m.group(0), m.start() + offset, m.end() + offset) for m in WORD.finditer(text)]


def content_stems(text: str) -> set[str]:
    out = set()
    for t in tokens(text):
        if t.text[0].isdigit() or t.low in STOPWORDS:
            continue
        for part in t.low.split("-"):
            if part and part not in STOPWORDS:
                out.add(stem(part))
        out.add(stem(t.low))
    return out


SENT_END = re.compile(r"[.!?][\"')\]]?\s+(?=[A-Z0-9\"'(\[À-Ý])")


def sentences(text: str) -> list[tuple[int, int]]:
    """Split a paragraph into (start, end) sentence spans."""
    spans, start = [], 0
    for m in SENT_END.finditer(text):
        before = text[start:m.start() + 1]
        last = re.findall(r"([A-Za-z.]+)\.$", before)
        if last and last[0].lower().rstrip(".") in ABBREVIATIONS:
            continue
        spans.append((start, m.start() + 1))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text.rstrip())))
    return [s for s in spans if s[1] > s[0]]


CLAUSE_BREAK = re.compile(
    r"[,;:()]|\s(?=(?:while|whereas|compared with|compared to|up from|down from|against|but)\b)", re.I)


def clauses(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split the sentence text[start:end] into clause spans (absolute offsets)."""
    spans, s = [], start
    for m in CLAUSE_BREAK.finditer(text, start, end):
        # do not split thousands separators like 3,284
        if m.group(0) == "," and m.start() > 0 and text[m.start() - 1].isdigit() and \
                m.start() + 1 < len(text) and text[m.start() + 1].isdigit():
            continue
        if m.start() > s:
            spans.append((s, m.start()))
        s = m.end()
    if end > s:
        spans.append((s, end))
    return spans


def contains_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", text, re.I) is not None


def find_phrase(text: str, phrase: str) -> list[int]:
    return [m.start() for m in re.finditer(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", text, re.I)]

"""Find numeric claims in a paragraph and parse their value, kind, precision and hedge.

Handles: 3,284 / 1.43 million / 1.2 thousand / 62% / 62 percent / 62 per cent / USD 1,200 /
spelled numbers (twelve, forty-two, one hundred and five) / fractions (half, a third, two thirds) /
hedges (nearly, over, about, at least, ...).

Ignores numbers that are not claims: dates, years, section and page references, phone numbers,
codes, durations, ages and measurements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Config
from .text import tokens

MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
          "dec"}
REF_WORDS = {"section", "sections", "chapter", "annex", "annexes", "appendix", "table", "figure", "fig", "page",
             "pages", "p", "pp", "sheet", "paragraph", "para", "version", "v", "output", "outcome", "result",
             "objective", "activity", "indicator", "phase", "step", "item", "line", "no", "grade", "level",
             "round", "cycle", "module", "article", "clause", "sdg", "room", "box", "route", "lot", "unit",
             "tranche", "batch", "wave", "year", "q"}
DURATION = {"day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours", "minute",
            "minutes", "yr", "yrs", "decade", "decades", "night", "nights", "-day", "-week", "-month", "-year"}
MEASURE = {"metre", "metres", "meter", "meters", "km", "kilometre", "kilometres", "kilometer", "kilometers",
           "litre", "litres", "liter", "liters", "kg", "kilogram", "kilograms", "tonne", "tonnes", "ton", "tons",
           "degree", "degrees", "cm", "mm", "hectare", "hectares", "ha", "mb", "gb", "°c", "m²", "m2", "m3",
           "sq"}
AGE_BEFORE = {"aged", "age", "ages", "agé"}
SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
CURRENCIES = {"usd": "usd", "us$": "usd", "$": "usd", "eur": "eur", "€": "eur", "gbp": "gbp", "£": "gbp",
              "kes": "kes", "ksh": "kes", "cop": "cop", "lbp": "lbp", "chf": "chf"}

ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90}
NUMBER_WORDS = set(ONES) | set(TENS) | {"hundred", "thousand"}

FRACTIONS = {
    ("", "half"): 50.0, ("a", "half"): 50.0, ("one", "half"): 50.0,
    ("a", "third"): 100 / 3, ("one", "third"): 100 / 3, ("two", "thirds"): 200 / 3,
    ("a", "quarter"): 25.0, ("one", "quarter"): 25.0, ("three", "quarters"): 75.0,
    ("a", "fifth"): 20.0, ("one", "fifth"): 20.0, ("two", "fifths"): 40.0, ("three", "fifths"): 60.0,
    ("four", "fifths"): 80.0,
}
FRACTION_RE = re.compile(
    r"(?<![\w-])(?:(a|one|two|three|four)\s+)?(half|thirds?|quarters?|fifths?)\s+of\b", re.I)
PHONE_RE = re.compile(r"(?<![\d,.])\+?\d{1,4}(?:[ \-]\d{1,4}){2,}(?!\d|,\d)")
AGE_RANGE_RE = re.compile(r"\b(?:aged|ages|age)\s+\d+\s*(?:to|-|–|and)\s*\d+", re.I)
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
NOT_PLURAL = {"was", "has", "does", "is", "this", "thus", "its", "his", "hers", "ours", "yours", "always",
              "perhaps", "across", "less", "unless", "plus", "as", "us", "yes", "gives", "takes", "makes",
              "comes", "goes", "becomes", "remains", "needs", "means", "serves", "lives", "includes"}


@dataclass
class Claim:
    id: str
    block: int
    start: int            # span of the whole claim text (hedge + currency + number + suffix)
    end: int
    num_start: int        # span of the number itself
    num_end: int
    text: str
    value: float          # counts and money as numbers; percentages and fractions in percent points
    kind: str             # count | money | percent | fraction
    precision: float      # half-width of the rounding window implied by how it is written
    hedge: str | None = None
    hedge_text: str | None = None
    currency: str | None = None
    spelled: bool = False
    sentence: tuple[int, int] = (0, 0)
    clause: tuple[int, int] = (0, 0)
    notes: list[str] = field(default_factory=list)


def _masks(text: str) -> list[tuple[int, int]]:
    spans = []
    for m in PHONE_RE.finditer(text):
        digits = sum(c.isdigit() for c in m.group(0))
        groups = len(re.split(r"[ \-]", m.group(0)))
        if digits >= 7 and (m.group(0).startswith("+") or groups >= 3):
            spans.append((m.start(), m.end()))
    for m in AGE_RANGE_RE.finditer(text):
        spans.append((m.start(), m.end()))
    return spans


def _word_before(text: str, pos: int) -> str:
    m = re.search(r"([A-Za-zÀ-ÿ$€£]+)\W{0,3}$", text[max(0, pos - 30):pos])
    return m.group(1).lower() if m else ""


def _adjacent_word_before(text: str, pos: int) -> str:
    """The word right before pos, with only spaces (or 'no.'/'p.' dots) in between."""
    m = re.search(r"([A-Za-zÀ-ÿ]+)\.?\s+$", text[max(0, pos - 30):pos])
    return m.group(1).lower() if m else ""


def _adjacent_word_after(text: str, pos: int) -> str:
    m = re.match(r"\s+([A-Za-zÀ-ÿ]+)", text[pos:pos + 30])
    return m.group(1).lower() if m else ""


def _word_after(text: str, pos: int) -> str:
    m = re.match(r"\s*([A-Za-zÀ-ÿ°²%-][A-Za-zÀ-ÿ²]*)", text[pos:pos + 30])
    return m.group(1).lower() if m else ""


def _hedge(text: str, pos: int, cfg: Config) -> tuple[str | None, str | None, int]:
    before = text[max(0, pos - 40):pos]
    low = before.lower()
    stripped = low.rstrip()
    for phrase, key in cfg.hedge_lookup:
        if stripped.endswith(phrase):
            i = len(stripped) - len(phrase)
            if i == 0 or not stripped[i - 1].isalnum():
                return key, before[i:len(stripped)], pos - (len(low) - i)
    return None, None, pos


def parse_number_text(s: str) -> float | None:
    """'3,284' -> 3284.0; rejects malformed thousands groups like '1,2'."""
    if "," in s:
        head, *groups = s.split(".")[0].split(",")
        if not (1 <= len(head) <= 3 and all(len(g) == 3 for g in groups)):
            return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def words_to_number(words: list[str]) -> int | None:
    total, current = 0, 0
    for w in words:
        for part in w.lower().split("-"):
            if part in ONES:
                current += ONES[part]
            elif part in TENS:
                current += TENS[part]
            elif part == "hundred":
                current = max(current, 1) * 100
            elif part == "thousand":
                total += max(current, 1) * 1000
                current = 0
            elif part == "and":
                continue
            else:
                return None
    return total + current


def extract_claims(text: str, block: int, cfg: Config, is_heading: bool = False) -> list[Claim]:
    """All numeric claims in one block of text, in order."""
    masks = _masks(text)
    taken: list[tuple[int, int]] = list(masks)
    out: list[Claim] = []

    def free(s, e):
        return not any(s < me and ms < e for ms, me in taken)

    # 1. fractions ("about a third of", "just over half of")
    for m in FRACTION_RE.finditer(text):
        lead = (m.group(1) or "").lower()
        frac = m.group(2).lower()
        if (lead, frac) not in FRACTIONS:
            continue
        if not lead and frac != "half":
            continue
        prev = _word_before(text, m.start())
        if frac == "half" and prev in ("first", "second", "the", "last"):
            continue
        end = m.start() + len(m.group(0)) - 3  # drop " of"
        end = len(text[:end].rstrip())
        hedge, htext, hstart = _hedge(text, m.start(), cfg)
        out.append(Claim("", block, hstart, end, m.start(), end, text[hstart:end], FRACTIONS[(lead, frac)],
                         "fraction", cfg.fraction_tol, hedge, htext))
        taken.append((m.start(), end))

    # 2. digits
    for m in NUM_RE.finditer(text):
        s, e = m.start(), m.end()
        raw = m.group(0)
        while raw.endswith(","):
            raw, e = raw[:-1], e - 1
        if not free(s, e):
            continue
        c0 = text[s - 1] if s > 0 else " "
        c1 = text[e] if e < len(text) else " "
        if c0.isalnum() or c0 in "/#" or c1.isalpha() or c1 in "/" or c0 == "+":
            continue
        if c0 in "-–" and s >= 2 and text[s - 2].isalnum():
            continue
        if c1 in "-–" and e + 1 < len(text) and text[e + 1].isalnum():
            continue
        if c1 == ":" and e + 1 < len(text) and text[e + 1].isdigit():
            continue
        if c1 == "." and e + 1 < len(text) and text[e + 1].isdigit():
            continue  # dotted section number like 3.1.2
        value = parse_number_text(raw)
        if value is None:
            continue
        if is_heading and not text[:s].strip(" ([").strip():
            continue  # heading numbering "3.1 Output ..."
        prev = _word_before(text, s)
        after = _word_after(text, e)
        adjacent_prev = _adjacent_word_before(text, s)
        if adjacent_prev in REF_WORDS or after in DURATION or after in MEASURE or prev in AGE_BEFORE:
            continue
        if adjacent_prev in MONTHS or _adjacent_word_after(text, e) in MONTHS:
            continue
        if "," not in raw and "." not in raw and len(raw) == 4 and 1900 <= value <= 2100:
            continue  # a year
        kind, end, precision = "count", e, 0.5
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if decimals:
            precision = 0.5 * 10 ** -decimals
        rest = text[e:e + 20]
        pm = re.match(r"\s*(%|percent\b|per\s+cent\b|pc\b)", rest, re.I)
        sm = re.match(r"\s*(thousand|million|billion)\b", rest, re.I)
        if pm:
            kind, end = "percent", e + pm.end()
        elif sm:
            mult = SCALES[sm.group(1).lower()]
            value *= mult
            precision *= mult
            end = e + sm.end()
        currency, start = None, s
        cm = re.search(r"(USD|US\$|\$|EUR|€|GBP|£|KES|KSh|COP|LBP|CHF)\s*$", text[max(0, s - 6):s])
        if cm:
            currency = CURRENCIES[cm.group(1).lower()]
            kind = "money"
            start = s - (len(text[max(0, s - 6):s]) - cm.start())
        hedge, htext, hstart = _hedge(text, start, cfg)
        out.append(Claim("", block, hstart, end, s, e, text[hstart:end], value, kind, precision, hedge, htext,
                         currency))
        taken.append((s, end))

    # 3. spelled numbers ("twelve surveys", "forty-two staff")
    toks = tokens(text)
    i = 0
    while i < len(toks):
        t = toks[i]
        parts = t.low.split("-")
        if not all(p in NUMBER_WORDS for p in parts) or not free(t.start, t.end) or parts[0] in ("hundred", "thousand"):
            i += 1
            continue
        j = i + 1
        while j < len(toks):
            nxt = toks[j].low
            gap = text[toks[j - 1].end:toks[j].start]
            if gap.strip():
                break
            if nxt in NUMBER_WORDS or (nxt == "and" and j + 1 < len(toks) and toks[j + 1].low in NUMBER_WORDS
                                       and "hundred" in [x.low for x in toks[i:j]]):
                j += 1
                continue
            break
        group = toks[i:j]
        value = words_to_number([g.text for g in group])
        i = j
        if value is None:
            continue
        s, e = group[0].start, group[-1].end
        prev = _word_before(text, s)
        if prev in ("a", "an") or prev in REF_WORDS or prev in AGE_BEFORE:
            continue
        follow = _following_words(text, toks, j, 3)
        if follow[:2] in (["of", "them"], ["of", "whom"], ["of", "these"], ["of", "those"]):
            follow = follow[2:] + _following_words(text, toks, j + 3, 1)
        if not follow:
            continue
        if follow[0] in DURATION or follow[0] in MEASURE or follow[0] == "of" or follow[0] in MONTHS:
            continue
        unit_like = [w for w in follow[:2] if (cfg.unit_of_word(w) and cfg.unit_of_word(w) not in CURRENCIES)
                     or w in cfg.sex_words]
        plural_like = [w for w in follow if len(w) > 3 and w.endswith("s") and not w.endswith("ss")
                       and w not in NOT_PLURAL]
        if value == 1:
            if not [w for w in follow[:2] if cfg.unit_of_word(w)]:
                continue
        elif not unit_like and not plural_like:
            continue
        hedge, htext, hstart = _hedge(text, s, cfg)
        out.append(Claim("", block, hstart, e, s, e, text[hstart:e], float(value), "count", 0.5, hedge, htext,
                         spelled=True))
        taken.append((s, e))

    out.sort(key=lambda c: c.num_start)
    for n, c in enumerate(out):
        c.id = f"b{block}-c{n}"
    return out


def _following_words(text, toks, j, n):
    words = []
    prev_end = toks[j - 1].end if j > 0 else 0
    for t in toks[j:j + n]:
        if re.search(r"[,;:.()]", text[prev_end:t.start]):
            break
        if t.text[0].isdigit():
            break
        words.append(t.low)
        prev_end = t.end
    return words

"""Load matching.toml into lookup tables."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .text import stem

DEFAULT_CONFIG = Path(__file__).parent / "config" / "matching.toml"

COLUMN_NAMES = {
    "indicator_id": ["indicator id", "id", "code", "indicator code", "ref", "reference"],
    "indicator": ["indicator", "indicator name", "indicator description", "description", "indicator title"],
    "unit": ["unit", "unit of measure", "uom", "units"],
    "period": ["period", "reporting period", "quarter", "reporting quarter"],
    "location": ["location", "governorate", "county", "district", "region", "area", "department",
                 "province", "site", "state"],
    "sex": ["sex", "gender", "sex/gender", "disaggregation"],
    "age": ["age group", "age", "age band", "age range"],
    "target": ["target", "planned", "plan", "target value"],
    "achieved": ["achieved", "actual", "result", "reached", "achievement", "actual value"],
}


@dataclass
class Config:
    units: dict[str, set[str]]              # canonical unit -> stems of words naming it
    unit_phrases: dict[str, list[str]]      # canonical unit -> multiword phrases (lowercase)
    person_units: set[str]
    sex_words: dict[str, str]               # lowercase word -> female|male
    synonyms: dict[str, set[str]]           # stem -> canonical stems
    synonym_phrases: dict[str, set[str]]    # multiword phrase -> canonical stems
    locations: dict[str, list[str]]         # canonical -> aliases
    all_locations: list[str]
    period_previous: list[str]
    period_cumulative: list[str]
    period_current: list[str]
    cues_future: list[str]
    cues_subset: list[str]
    cues_target: list[str]
    hedges: dict[str, dict]                 # key -> {words, low, high, strict_low, strict_high}
    age_words: dict[str, str] = field(default_factory=dict)     # lowercase word/phrase -> children|adults|older
    stock: dict[str, list[str]] = field(default_factory=dict)  # cue lists for the stock path
    hedge_lookup: list[tuple[str, str]] = field(default_factory=list)  # (phrase, key), longest first
    fraction_tol: float = 2.5
    fraction_tol_hedged: float = 4.0
    min_score: float = 1.0
    min_margin: float = 0.5
    context_weight: float = 0.5

    def unit_of_word(self, word: str) -> str | None:
        s = stem(word)
        for unit, stems in self.units.items():
            if s in stems:
                return unit
        return None

    def canonical_unit(self, unit_cell: str) -> str:
        """Map a workbook unit cell ("Households", "%", "USD") to a canonical unit."""
        u = (unit_cell or "").strip().lower()
        if u in ("%", "percent", "percentage", "per cent", "rate"):
            return "percent"
        if u in self.units:
            return u
        found = self.unit_of_word(u)
        if found:
            return found
        # Unknown unit: it becomes its own canonical unit, named by its stem.
        s = stem(u)
        self.units.setdefault(s, {s})
        return s


def _load(path: Path) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    units, unit_phrases = {}, {}
    for unit, words in raw["units"].items():
        if unit == "person_units":
            continue
        units[unit] = {stem(w) for w in words if " " not in w}
        units[unit].add(stem(unit))
        unit_phrases[unit] = [w.lower() for w in words if " " in w]
    sex_words = {}
    for sex, words in raw["sex"].items():
        for w in words:
            sex_words[w.lower()] = sex
    synonyms, synonym_phrases = {}, {}
    for canon, words in raw["synonyms"].items():
        c = stem(canon)
        synonyms.setdefault(c, set()).add(c)
        for w in words:
            if " " in w:
                synonym_phrases.setdefault(w.lower(), set()).add(c)
            else:
                synonyms.setdefault(stem(w), set()).add(c)
    hedges, lookup = {}, []
    for key, h in raw["hedges"].items():
        hedges[key] = h
        for w in h["words"]:
            lookup.append((w.lower(), key))
    lookup.sort(key=lambda p: -len(p[0]))
    locs = {k: v for k, v in raw["locations"].items() if k != "all_locations"}
    m = raw["match"]
    age_words = {}
    for group, ws in raw.get("age", {}).items():
        for w in ws:
            age_words[w.lower()] = group
    stock = {k: [w.lower() for w in v] for k, v in raw.get("stock", {}).items()}
    return Config(
        age_words=age_words, stock=stock,
        units=units, unit_phrases=unit_phrases, person_units=set(raw["units"]["person_units"]),
        sex_words=sex_words, synonyms=synonyms, synonym_phrases=synonym_phrases, locations=locs,
        all_locations=[w.lower() for w in raw["locations"]["all_locations"]],
        period_previous=[w.lower() for w in raw["periods"]["previous"]],
        period_cumulative=[w.lower() for w in raw["periods"]["cumulative"]],
        period_current=[w.lower() for w in raw["periods"]["current"]],
        cues_future=[w.lower() for w in raw["cues"]["future"]],
        cues_subset=[w.lower() for w in raw["cues"]["subset"]],
        cues_target=[w.lower() for w in raw["cues"]["target"]],
        hedges=hedges, hedge_lookup=lookup,
        fraction_tol=raw["fractions"]["tolerance_points"],
        fraction_tol_hedged=raw["fractions"]["hedged_tolerance_points"],
        min_score=m["min_score"], min_margin=m["min_margin"], context_weight=m["context_weight"],
    )


@lru_cache(maxsize=8)
def load_config(path: str | None = None) -> Config:
    return _load(Path(path) if path else DEFAULT_CONFIG)

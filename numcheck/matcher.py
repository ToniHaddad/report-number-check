"""Work out what each claim is about: indicator, measure, location, period and sex.

Everything is decided from the words around the number, the previous sentence,
the section heading and matching.toml. When the evidence is weak the claim is
left unmatched (and reported as unverifiable) rather than guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import Config
from .numbers import Claim
from .text import STOPWORDS, Token, content_stems, contains_phrase, find_phrase, stem, tokens
from .workbook import Indicator, Workbook, period_phrases

BREAK_WORDS = {"were", "was", "are", "is", "have", "has", "had", "received", "in", "at", "from", "with", "who",
               "which", "that", "and", "to", "by", "for", "of", "this", "against", "on", "across", "per",
               "during", "through", "or", "than", "while", "since", "over", "under", "between", "after",
               "before", "because", "so", "but", "took", "attended", "completed", "now", "still", "had"}
SKIP_AFTER = {"of", "them", "whom", "were", "are", "was", "being", "these", "those", "who", "the"}
ANAPHORS = ("this", "that", "it", "these", "which", "together", "overall", "altogether")
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]


@dataclass
class Interpretation:
    indicator: Indicator | None = None
    measure: str = "achieved"          # achieved | target | pct_target | share | rate
    periods: list[str] = field(default_factory=list)
    period_how: str = "default (current period)"
    locations: list[str] | None = None  # None means all locations
    location_how: str = "none mentioned: all locations"
    sex: str | None = None              # female | male | None (both)
    unit: str | None = None
    score: float = 0.0
    runner_up: tuple[str, float] | None = None
    keyword_hits: list[str] = field(default_factory=list)
    via: str = ""                       # how the indicator was chosen
    unverifiable: str | None = None     # reason, when no safe match exists


@dataclass
class Context:
    """A claim with the text around it."""
    claim: Claim
    block_text: str
    sentence: str
    sentence_start: int
    clause: str
    clause_start: int
    prev_sentence: str
    heading: str
    sentence_claims: list[Claim]        # claims in the same sentence, in order


class Matcher:
    def __init__(self, wb: Workbook, cfg: Config):
        self.wb = wb
        self.cfg = cfg
        self.unit_stems = set().union(*cfg.units.values()) | {"percent", "%"}
        self.sex_stems = {stem(w) for w in cfg.sex_words}
        loc_stems = set()
        for loc in wb.locations:
            loc_stems |= content_stems(loc)
        self.keywords = {}
        self.kw_word: dict[str, dict[str, str]] = {}
        for ind in wb.indicators.values():
            kws = content_stems(ind.name) - self.unit_stems - self.sex_stems - loc_stems
            kws = {k for k in kws if not k[0].isdigit() and k not in STOPWORDS and len(k) > 1}
            self.keywords[ind.id] = kws
            words = {}
            for t in tokens(ind.name):
                for part in [t.low] + t.low.split("-"):
                    words.setdefault(stem(part), part)
            self.kw_word[ind.id] = words
        # location name -> list of regex-able aliases
        self.loc_aliases: dict[str, list[str]] = {}
        for loc in wb.locations:
            aliases = {loc}
            for canon, al in cfg.locations.items():
                if canon.lower() == loc.lower():
                    aliases |= set(al)
            self.loc_aliases[loc] = sorted(aliases, key=len, reverse=True)
        self.prev_period = wb.previous_period
        self.cur_period = wb.current_period

    # ------------------------------------------------------------ helpers

    def expand(self, stems: set[str], text: str = "") -> set[str]:
        out = set()
        for s in stems:
            out.add(s)
            out |= self.cfg.synonyms.get(s, set())
        low = text.lower()
        for phrase, canon in self.cfg.synonym_phrases.items():
            if phrase in low:
                out |= canon
        return out

    def score(self, ind: Indicator, sentence: str, context: str) -> tuple[float, list[str]]:
        sent = self.expand(content_stems(sentence), sentence)
        ctx = self.expand(content_stems(context), context)
        total, hits = 0.0, []
        for k in sorted(self.keywords[ind.id]):
            ek = self.expand({k})
            word = self.kw_word.get(ind.id, {}).get(k, k)
            if ek & sent:
                total += 1.0
                hits.append(word)
            elif ek & ctx:
                total += self.cfg.context_weight
                hits.append(f"{word} (nearby)")
        return total, hits

    def pick(self, cands: list[Indicator], ctx: Context, interp: Interpretation, why: str) -> bool:
        if not cands:
            interp.unverifiable = interp.unverifiable or f"no indicator in the workbook {why}"
            return False
        context = ctx.prev_sentence + " " + ctx.heading
        scored = []
        for ind in cands:
            s, hits = self.score(ind, ctx.sentence, context)
            scored.append((s, ind, hits))
        scored.sort(key=lambda x: -x[0])
        best_s, best, hits = scored[0]
        second = scored[1] if len(scored) > 1 else None
        interp.score = best_s
        interp.keyword_hits = hits
        if second:
            interp.runner_up = (second[1].id, second[0])
        if best_s < self.cfg.min_score:
            interp.unverifiable = (f"weak match: best indicator {best.id} scored {best_s:g} on keywords "
                                   f"(needs {self.cfg.min_score:g})")
            return False
        if second and best_s - second[0] < self.cfg.min_margin:
            interp.unverifiable = (f"ambiguous: {best.id} ({best_s:g}) and {second[1].id} ({second[0]:g}) "
                                   f"match equally well")
            return False
        interp.indicator = best
        interp.via = f"keywords {', '.join(hits)}"
        return True

    def clause_tokens_after(self, ctx: Context, n: int) -> list[Token]:
        c = ctx.claim
        clause_end = ctx.clause_start + len(ctx.clause)
        toks = tokens(ctx.block_text[c.end:clause_end], c.end)
        return toks[:n]

    def clause_tokens_before(self, ctx: Context, n: int) -> list[Token]:
        c = ctx.claim
        toks = tokens(ctx.block_text[ctx.clause_start:c.start], ctx.clause_start)
        return toks[-n:] if n else []

    # ------------------------------------------------------------ unit, sex, measure

    def detect_unit(self, ctx: Context) -> tuple[str | None, bool]:
        """(unit, unknown_noun): the unit named right after the number, or a sign
        that the number counts something the workbook has no unit for."""
        c = ctx.claim
        if c.kind == "money":
            return (c.currency if c.currency in self.cfg.units else c.currency), False
        after = self.clause_tokens_after(ctx, 5)
        after_text = ctx.block_text[c.end:c.end + 40].lower()
        for unit, phrases in self.cfg.unit_phrases.items():
            for p in phrases:
                if re.match(r"\s*(?:[a-z-]+\s+){0,2}" + re.escape(p) + r"\b", after_text):
                    return unit, False
        found, unknown = None, False
        for i, t in enumerate(after):
            w = t.low
            if t.text[0].isdigit():
                break
            if c.kind in ("percent", "fraction") and i == 0 and w == "of":
                continue
            if c.kind in ("percent", "fraction") and w in ("the", "all", "surveyed", "enrolled", "assisted",
                                                           "those", "these", "them"):
                continue
            u = self.cfg.unit_of_word(w)
            if u:
                found = u
                continue
            if w in self.cfg.sex_words:
                break
            if w in BREAK_WORDS or w in STOPWORDS:
                break
            if i == 0 and c.kind in ("count",):
                unknown = True
        if found:
            return found, False
        return None, unknown and c.kind == "count"

    def detect_sex(self, ctx: Context) -> str | None:
        c = ctx.claim
        after = self.clause_tokens_after(ctx, 6)
        steps = 0
        for t in after:
            if t.low in self.cfg.sex_words:
                return self.cfg.sex_words[t.low]
            if t.low in SKIP_AFTER or self.cfg.unit_of_word(t.low) in self.cfg.person_units:
                continue
            steps += 1
            if steps > 1 or t.text[0].isdigit():
                break
        if c.kind in ("percent", "fraction"):
            for t in tokens(ctx.clause):
                if t.low in self.cfg.sex_words:
                    return self.cfg.sex_words[t.low]
            return None
        before = self.clause_tokens_before(ctx, 4)
        for t in reversed(before):
            if t.text[0].isdigit():
                break
            if t.low in self.cfg.sex_words:
                return self.cfg.sex_words[t.low]
        return None

    def target_before(self, ctx: Context) -> bool:
        before = " ".join(t.low for t in self.clause_tokens_before(ctx, 4))
        return any(re.search(r"\b" + re.escape(cue) + r"\b", before) for cue in self.cfg.cues_target)

    def target_after(self, ctx: Context) -> bool:
        c = ctx.claim
        clause_end = ctx.clause_start + len(ctx.clause)
        after = ctx.block_text[c.end:clause_end].lower()
        return any(re.search(r"\b" + re.escape(cue) + r"\b", after) for cue in self.cfg.cues_target)

    # ------------------------------------------------------------ location and period

    def location_mentions(self, text: str, offset: int) -> list[tuple[int, int, str]]:
        out = []
        for loc, aliases in self.loc_aliases.items():
            for a in aliases:
                for pos in find_phrase(text, a):
                    s, e = pos + offset, pos + offset + len(a)
                    if not any(s < oe and os < e for os, oe, _ in out):
                        out.append((s, e, loc))
        return sorted(out)

    def resolve_location(self, ctx: Context, interp: Interpretation, inherited: list[str] | None,
                         has_inherited: bool) -> None:
        c = ctx.claim
        text = ctx.block_text
        mentions = self.location_mentions(ctx.sentence, ctx.sentence_start)
        clause_end = ctx.clause_start + len(ctx.clause)
        low_clause = ctx.clause.lower()
        if self._says_all_locations(low_clause):
            interp.locations, interp.location_how = None, "all locations (stated)"
            return
        lists = _group_lists(text, mentions)
        others = [o for o in ctx.sentence_claims if o is not c]

        def between_has_number(a, b):
            return any(a <= o.num_start < b or a < o.num_end <= b for o in others)

        chosen = None
        in_clause = [m for m in mentions if ctx.clause_start <= m[0] < clause_end]
        before = [m for m in in_clause if m[1] <= c.start and not between_has_number(m[1], c.start)]
        after = [m for m in in_clause if m[0] >= c.end and not between_has_number(c.end, m[0])]
        right_after = [m for m in after if re.fullmatch(
            r"\s*(?:[a-z-]+\s+){0,2}?(?:in|at|for|from)\s+(?:the\s+)?", text[c.end:m[0]].lower())]
        if right_after:
            chosen, how = right_after[0], "named right after the number"
        elif before:
            chosen, how = before[-1], "named before the number in the same clause"
        elif after:
            chosen, how = after[0], "named after the number in the same clause"
        else:
            prior = [m for m in mentions if m[1] <= c.start and not between_has_number(m[1], c.start)]
            if prior:
                chosen, how = prior[-1], "named earlier in the sentence"
        if chosen is not None:
            group = next((g for g in lists if chosen in g), [chosen])
            locs = [m[2] for m in group]
            if set(locs) >= set(self.wb.locations):
                interp.locations, interp.location_how = None, "all locations (all named in a list)"
            else:
                interp.locations, interp.location_how = locs, how
            return
        if has_inherited:
            interp.locations = inherited
            interp.location_how = "same as the figure it refers to"
            return
        if self._says_all_locations(self._numberless_clauses_text(ctx)):
            interp.locations, interp.location_how = None, "all locations (stated in the sentence)"
            return
        if mentions:
            locs = sorted({m[2] for m in mentions})
            # Every location in the sentence has its own figure next to it: this one is the total.
            taken = [m for m in mentions if any(abs(o.num_start - m[1]) < 25 or abs(m[0] - o.num_end) < 25
                                                for o in others)]
            if len(taken) == len(mentions) and len(others) >= 2:
                interp.locations = None
                interp.location_how = "all locations: the other figures in the sentence are per location"
                return
            free =[m for m in mentions if not any(
                o.num_start >= m[0] and o.num_start <= m[1] + 60 for o in others)]
            if len(locs) == 1 and free:
                interp.locations, interp.location_how = locs, "only location named in the sentence"
                return
            interp.unverifiable = interp.unverifiable or ("location unclear: the sentence names "
                                                          + ", ".join(locs))
            return
        head = self.location_mentions(ctx.heading, 0)
        if len({m[2] for m in head}) == 1:
            interp.locations, interp.location_how = [head[0][2]], "named in the section heading"

    def _says_all_locations(self, low: str) -> bool:
        return any(contains_phrase(low, cue) for cue in self.cfg.all_locations) or \
            re.search(r"\bacross\b", low) is not None

    def _numberless_clauses_text(self, ctx: Context) -> str:
        parts = []
        for s, e in _clause_spans_of(ctx):
            if not any(s <= o.num_start < e for o in ctx.sentence_claims):
                parts.append(ctx.block_text[s:e].lower())
        return " | ".join(parts)

    def _period_in(self, text: str) -> tuple[list[str], str] | None:
        low = text.lower()
        for p in self.wb.periods:
            for ph in period_phrases(p):
                if contains_phrase(low, ph):
                    return [p], f"'{ph}' names {p}"
        if re.search(r"\bsince\s+(?:" + "|".join(MONTHS) + r"|q[1-4]\b|the\s+\w+\s+quarter)", low) or \
                any(contains_phrase(low, ph) for ph in self.cfg.period_cumulative):
            return [p for p in self.wb.periods], "cumulative (all periods to date)"
        for ph in self.cfg.period_previous:
            if contains_phrase(low, ph) and self.prev_period:
                return [self.prev_period], f"'{ph}' points to {self.prev_period}"
        return None

    def resolve_period(self, ctx: Context, interp: Interpretation, inherited: list[str] | None) -> None:
        found = self._period_in(ctx.clause)
        if found is None:
            # A period named in a clause without its own number applies to the sentence.
            clause_spans = _clause_spans_of(ctx)
            for s, e in clause_spans:
                if any(s <= o.num_start < e for o in ctx.sentence_claims):
                    continue
                f = self._period_in(ctx.block_text[s:e])
                if f:
                    found = f
                    break
        if found:
            interp.periods, interp.period_how = found
        elif inherited:
            interp.periods, interp.period_how = inherited, "same as the figure it refers to"
        else:
            interp.periods, interp.period_how = [self.cur_period], f"current period ({self.cur_period})"

    # ------------------------------------------------------------ main

    def interpret(self, ctx: Context, resolved: dict[str, Interpretation],
                  prev_sentence_claims: list[Claim]) -> Interpretation:
        c = ctx.claim
        it = Interpretation()
        low_clause = ctx.clause.lower()
        for cue in self.cfg.cues_future:
            if contains_phrase(low_clause, cue):
                it.unverifiable = f"describes a plan ('{cue}'), not a result"
                return it
        for cue in self.cfg.cues_subset:
            if contains_phrase(low_clause, cue):
                it.unverifiable = f"describes a subset or rate the workbook does not record ('{cue}')"
                return it

        unit, unknown_noun = self.detect_unit(ctx)
        sex = self.detect_sex(ctx)
        it.unit, it.sex = unit, sex
        earlier = [resolved[o.id] for o in ctx.sentence_claims if o.num_start < c.num_start
                   and o.id in resolved and resolved[o.id].indicator is not None]
        earlier_achieved = [e for e in earlier if e.measure == "achieved"]
        antecedent = earlier[-1] if earlier else None
        ante_achieved = earlier_achieved[-1] if earlier_achieved else None
        if antecedent is None and prev_sentence_claims and \
                ctx.sentence.strip().lower().startswith(ANAPHORS):
            # "This is 89 percent of the target" refers to the main figure of the previous sentence.
            prior = [resolved[o.id] for o in prev_sentence_claims if o.id in resolved
                     and resolved[o.id].indicator and resolved[o.id].measure == "achieved"]
            if prior:
                antecedent = ante_achieved = prior[0]
        inherited = False
        inds = list(self.wb.indicators.values())

        if c.kind in ("percent", "fraction"):
            if self.target_before(ctx):
                it.measure = "target"
                cand_ante = antecedent
                if cand_ante and cand_ante.indicator.rate:
                    self._inherit(it, cand_ante)
                    inherited = True
                else:
                    it.unverifiable = "a target stated as a percentage, but no rate indicator to attach it to"
                    return it
            elif self.target_after(ctx):
                it.measure = "pct_target"
                if ante_achieved and not ante_achieved.indicator.rate:
                    antecedent = ante_achieved
                    self._inherit(it, antecedent)
                    inherited = True
                else:
                    cands = [i for i in inds if not i.rate and i.has_target]
                    if not self.pick(cands, ctx, it, "has a target"):
                        return it
            elif sex:
                it.measure = "share"
                if ante_achieved and ante_achieved.indicator.has_sex:
                    antecedent = ante_achieved
                    self._inherit(it, antecedent)
                    it.sex = sex
                    inherited = True
                else:
                    cands = [i for i in inds if i.has_sex and not i.rate and (unit is None or i.unit == unit)]
                    if not self.pick(cands, ctx, it, "is broken down by sex"):
                        return it
            else:
                it.measure = "rate"
                cands = [i for i in inds if i.rate]
                if unit and unit != "percent":
                    vocab = self.cfg.units.get(unit, set())
                    cands = [i for i in cands if content_stems(i.name) & vocab]
                if not self.pick(cands, ctx, it, "is a percentage" + (f" of {unit}" if unit else "")):
                    return it
        else:
            target = self.target_before(ctx)
            it.measure = "target" if target else "achieved"
            if unknown_noun:
                it.unverifiable = "counts something the workbook has no unit for"
                return it
            if unit is None and sex is None:
                if antecedent and not antecedent.indicator.rate:
                    self._inherit(it, antecedent, keep_measure=False)
                    inherited = True
                else:
                    # "Of these, 214 were closed": take the unit of the previous sentence's last figure
                    lead_in = ctx.block_text[ctx.sentence_start:c.start].lower()
                    if prev_sentence_claims and re.search(r"\b(these|them|those|whom)\b", lead_in):
                        prior = [o for o in prev_sentence_claims if o.id in resolved and resolved[o.id].unit]
                        if prior:
                            unit = resolved[prior[-1].id].unit
                    if unit is None:
                        it.unverifiable = "no unit next to the number and nothing earlier in the sentence to refer to"
                        return it
            if not inherited:
                if unit is None and sex:
                    if antecedent and antecedent.indicator.has_sex:
                        self._inherit(it, antecedent, keep_measure=False)
                        it.sex = sex
                        inherited = True
                    else:
                        cands = [i for i in inds if i.has_sex and i.unit in self.cfg.person_units and not i.rate]
                        if not self.pick(cands, ctx, it, "counts people by sex"):
                            return it
                else:
                    if sex and unit not in self.cfg.person_units:
                        sex = None
                    it.unit, it.sex = unit, sex
                    cands = [i for i in inds if i.unit == unit and not i.rate]
                    if not self.pick(cands, ctx, it, f"counts {unit}"):
                        # The previous sentence counted the same unit for one indicator:
                        # this sentence continues it ("Akkar accounted for 1,204 households, ...").
                        prior = [resolved[o.id] for o in prev_sentence_claims if o.id in resolved
                                 and resolved[o.id].indicator is not None
                                 and resolved[o.id].indicator.unit == unit
                                 and resolved[o.id].measure == "achieved"]
                        if not prior or it.unverifiable.startswith("ambiguous") or \
                                len({p.indicator.id for p in prior}) != 1:
                            return it
                        it.unverifiable = None
                        it.indicator = prior[-1].indicator
                        it.via = f"continues the previous sentence ({it.indicator.id})"
            if target and not it.indicator.has_target:
                it.unverifiable = f"{it.indicator.id} has no target in the workbook"
                return it

        if it.sex and not it.indicator.has_sex:
            it.unverifiable = f"{it.indicator.id} is not broken down by sex in the workbook"
            return it
        ante_locs = antecedent.locations if (inherited and antecedent) else None
        ante_periods = antecedent.periods if (inherited and antecedent) else None
        self.resolve_location(ctx, it, ante_locs, inherited)
        if it.unverifiable:
            return it
        self.resolve_period(ctx, it, ante_periods)
        return it

    def _inherit(self, it: Interpretation, ante: Interpretation, keep_measure: bool = True) -> None:
        it.indicator = ante.indicator
        it.sex = ante.sex
        it.unit = ante.unit
        it.score = ante.score
        it.keyword_hits = ante.keyword_hits
        it.via = f"refers to the figure before it ({ante.indicator.id})"


def _group_lists(text: str, mentions):
    """Group location mentions written as a list: 'Akkar, Tripoli and the Bekaa'."""
    groups, cur = [], []
    for m in mentions:
        if cur and re.fullmatch(r"[\s,]*(?:and|&|or)?\s*(?:the)?\s*", text[cur[-1][1]:m[0]], re.I):
            cur.append(m)
        else:
            if cur:
                groups.append(cur)
            cur = [m]
    if cur:
        groups.append(cur)
    return [g for g in groups if len(g) > 1]


def _clause_spans_of(ctx: Context):
    from .text import clauses
    return clauses(ctx.block_text, ctx.sentence_start, ctx.sentence_start + len(ctx.sentence))

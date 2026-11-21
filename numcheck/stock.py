"""Claims about stock and dispatches: matched to the dispatch summary and stock sheets.

A claim goes this way when it names a stock item ("hygiene kits", "boxes of canned cheese") or
counts pieces or boxes, and the sentence talks about warehouses, dispatches, stock or donations,
or names a warehouse or a destination. The same weak-match rule applies: if the item, the
warehouse or the destination cannot be told apart, the claim stays unverifiable.
"""
from __future__ import annotations

import re

from .config import Config
from .text import contains_phrase, stem, tokens
from .workbook import Item, Workbook, period_phrases

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
SIZE = re.compile(r"^\d|^(kg|g|l|ml|cm|m)$", re.I)
NP_BREAK = {"were", "was", "are", "is", "from", "to", "for", "in", "at", "on", "and", "with", "this", "over",
            "during", "by", "which", "that", "who", "left", "went", "of", "a", "an", "the", "had", "have", "has"}


def _item_stems(item: Item) -> list[str]:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", item.name) if not SIZE.match(w)]
    return [stem(w) for w in words]


def _phrase_regex(name: str) -> re.Pattern:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", name)]
    gap = r"\W+(?:\w+\W+){0,3}?"
    return re.compile(r"(?<!\w)" + gap.join(re.escape(w) for w in words) + r"(?!\w)", re.I)


class StockMatcher:
    def __init__(self, wb: Workbook, cfg: Config):
        self.wb, self.cfg = wb, cfg
        self.items = list(wb.items.values())
        self.item_stems = {i.code: _item_stems(i) for i in self.items}
        self.dest_re = {d: _phrase_regex(d) for d in wb.destinations}
        self.wh_re = {}
        for w in wb.warehouses:
            code = re.match(r"(WH)-?0*(\d+)", w, re.I)
            place = re.sub(r"^WH-?\d+\s*", "", w).strip()
            pats = []
            if code:
                pats.append(r"WH-?0*" + code.group(2) + r"(?!\d)")
            if place:
                pats.append(re.escape(place) + r"\s+warehouse")
            self.wh_re[w] = re.compile("|".join(f"(?:{p})" for p in pats), re.I)

    @property
    def enabled(self) -> bool:
        return bool(self.items) and (self.wb.dispatch is not None or self.wb.stock is not None)

    # ------------------------------------------------------------ pieces of evidence

    def noun_phrase(self, ctx) -> tuple[list[str], str | None]:
        """Stems of the words naming what the number counts, and a packaging unit if any."""
        c = ctx.claim
        after = ctx.block_text[c.end:c.end + 80]
        low = after.lower().lstrip()
        unit = None
        if c.extra_pieces is not None:
            unit = "boxes"
            low = re.sub(r"^of\s+", "", low)
        for p in self.cfg.stock.get("packaging", []):
            if low.startswith(p + " "):
                unit = "boxes" if p.split()[0] in ("boxes", "box", "bales", "bale", "cartons", "carton") else "pieces"
                low = low[len(p) + 1:]
                break
        words, prev_end = [], 0
        for t in tokens(low)[:5]:
            if t.text[0].isdigit() or t.low in NP_BREAK or re.search(r"[,;:.()|]", low[prev_end:t.start]):
                break
            prev_end = t.end
            words.append(t.low)
            u = self.cfg.unit_of_word(t.low)
            if u in ("boxes", "pieces") and unit is None and len(words) == 1:
                unit = u
        return [stem(w) for w in words], unit

    def header_unit(self, ctx) -> str | None:
        """In a table row, the column header right before the number ("Boxes: 458")."""
        before = ctx.block_text[ctx.clause_start:ctx.claim.start].lower()
        for w in reversed(re.findall(r"[a-z]+", before)):
            u = self.cfg.unit_of_word(w)
            if u in ("boxes", "pieces"):
                return u
        return None

    def find_items(self, stems: list[str], text: str) -> list[Item]:
        if stems:
            scored = []
            for it in self.items:
                its = self.item_stems[it.code]
                if its and its[-1] in stems:
                    scored.append((sum(1 for s in its if s in stems), it))
            if scored:
                best = max(s for s, _ in scored)
                cands = [it for s, it in scored if s == best]
                if len(cands) > 1:   # e.g. "kits": use the rest of the sentence
                    sent = {stem(t.low) for t in tokens(text)}
                    sc = [(sum(1 for s in self.item_stems[it.code] if s in sent), it) for it in cands]
                    top = max(s for s, _ in sc)
                    cands = [it for s, it in sc if s == top]
                return cands
            return []
        # no noun after the number: an item named in the sentence
        sent = {stem(t.low) for t in tokens(text)}
        found = [it for it in self.items if self.item_stems[it.code] and self.item_stems[it.code][-1] in sent
                 and sum(1 for s in self.item_stems[it.code] if s in sent) >= max(1, len(self.item_stems[it.code]) - 1)]
        return found

    def mentions(self, regs: dict, text: str, offset: int):
        out = []
        for name, rx in regs.items():
            for m in rx.finditer(text):
                out.append((m.start() + offset, m.end() + offset, name))
        out.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        keep = []
        for m in out:   # drop a mention inside a longer one ("Zahle centre" inside "Social department, Zahle centre")
            if any(k[0] <= m[0] and m[1] <= k[1] and k != m for k in out if (k[1] - k[0]) > (m[1] - m[0])):
                continue
            keep.append(m)
        return keep

    def pick_mention(self, ms, ctx):
        """The mention nearest before the claim with no other number between; else in its clause."""
        if not ms:
            return None
        c = ctx.claim
        others = [o for o in ctx.sentence_claims if o is not c]

        def clear(a, b):
            return not any(a <= o.num_start < b for o in others)
        if ctx.is_row:
            names = {m[2] for m in ms}
            return ms[0][2] if len(names) == 1 else "AMBIGUOUS"
        before = [m for m in ms if m[1] <= c.start and clear(m[1], c.start)]
        if before:
            return before[-1][2]
        clause_end = ctx.clause_start + len(ctx.clause)
        after = [m for m in ms if c.end <= m[0] < clause_end and clear(c.end, m[0])]
        if after:
            return after[0][2]
        names = {m[2] for m in ms}
        free = [m for m in ms if clear(min(m[1], c.start), max(m[0], c.end))]
        if len(names) == 1 and free:
            return ms[0][2]
        return "AMBIGUOUS" if names else None

    def has(self, text: str, key: str) -> bool:
        low = text.lower()
        return any(contains_phrase(low, w) for w in self.cfg.stock.get(key, []))

    # ------------------------------------------------------------ main

    def interpret(self, ctx, it, resolved, prev_claims) -> bool:
        """Fill `it` for a stock or dispatch claim. Returns False when the claim is not one."""
        if not self.enabled or ctx.claim.kind not in ("count",):
            return False
        c = ctx.claim
        stems, unit = self.noun_phrase(ctx)
        unit = unit or (self.header_unit(ctx) if ctx.is_row else None)
        sentence = ctx.sentence
        whs = self.mentions(self.wh_re, sentence, ctx.sentence_start)
        dests = self.mentions(self.dest_re, sentence, ctx.sentence_start)
        signal = bool(whs or dests) or self.has(sentence, "signal")
        earlier = [resolved[o.id] for o in ctx.sentence_claims if o.num_start < c.num_start and o.id in resolved]
        stock_ante = next((e for e in reversed(earlier) if e.source in ("dispatch", "stock") and e.item), None)
        np_items = self.find_items(stems, sentence) if stems else []
        np_named_other = bool(stems) and not np_items and unit is None
        if not signal:
            return False
        if np_named_other:
            # the number counts something that is not a stock item (households, people, villages)
            if any(self.cfg.unit_of_word(w) for w in [s for s in stems]):
                return False
            if not stock_ante:
                return False
        if not np_items and unit is None and not stock_ante and not ctx.is_row:
            return False

        it.source = "stock"   # refined below
        items = np_items or self.find_items([], sentence)
        if not items and stock_ante:
            items = [stock_ante.item]
        if len(items) != 1:
            it.unverifiable = ("no stock item named next to the figure" if not items else
                               "item unclear: " + ", ".join(i.name for i in items))
            return True
        it.item = items[0]
        it.unit = unit or "pieces"
        if c.extra_pieces is not None:
            it.unit = "boxes"

        # which measure
        clause, low_sent = ctx.clause.lower(), sentence.lower()
        before = ctx.block_text[ctx.clause_start:c.start].lower()
        wh = self.pick_mention(whs, ctx)
        dest = self.pick_mention(dests, ctx)
        if self.has(clause, "closing") or (not dest and self.has(before[-40:], "closing")):
            measure = "closing"
        elif self.has(clause, "opening"):
            measure = "opening"
        elif dest and dest != "AMBIGUOUS":
            measure = "dispatched"
        elif self.has(clause, "received") and not self.has(clause, "dispatch"):
            measure = "received_inkind" if self.has(clause, "inkind") or self.has(low_sent, "inkind") \
                and not self.has(clause, "purchase") else "received"
            if self.has(clause, "purchase"):
                measure = "received_purchase"
        elif self.has(clause, "dispatch") or self.has(before, "dispatch") or (ctx.is_row and self.has(low_sent, "dispatch")):
            measure = "dispatched"
        elif stock_ante and stock_ante.measure in ("received", "received_inkind", "dispatched", "closing", "opening"):
            measure = stock_ante.measure
        elif self.has(low_sent, "dispatch"):
            measure = "dispatched"
        else:
            it.unverifiable = "a stock figure, but not clear whether received, dispatched or in stock"
            return True
        it.measure = measure
        if dest == "AMBIGUOUS":
            it.unverifiable = "destination unclear: the sentence names several"
            return True
        if wh == "AMBIGUOUS":
            it.unverifiable = "warehouse unclear: the sentence names several"
            return True
        if wh is None and stock_ante and stock_ante.warehouses:
            it.warehouses = stock_ante.warehouses
            it.location_how = "same warehouse as the figure before it"
        else:
            it.warehouses = [wh] if wh else None
            it.location_how = "named in the sentence" if wh else "no warehouse named: all warehouses"
        it.destinations = [dest] if dest and measure == "dispatched" else None
        if measure == "dispatched" and self.wb.dispatch is not None:
            it.source = "dispatch"
        elif self.wb.stock is not None:
            it.source = "stock"
        else:
            it.unverifiable = "the workbook has no sheet for this kind of stock figure"
            return True

        # period or month
        month = self._month(ctx)
        if month and it.source == "dispatch":
            it.months = [month]
            it.periods = [p for p in self.wb.periods if _quarter_of(month) == _q(p)] or [self.wb.current_period]
            it.period_how = f"'{month.title()}' (month filter on the dispatch sheet)"
        else:
            self._period(ctx, it, stock_ante)
        it.via = f"item '{it.item.name}'" + (f", destination {dest}" if it.destinations else "") + \
            (f", warehouse {it.warehouses[0]}" if it.warehouses else "")
        return True

    def _month(self, ctx) -> str | None:
        text = ctx.clause.lower()
        found = [m for m in MONTHS if re.search(r"\b" + m + r"\b", text)]
        if not found:
            sent = ctx.sentence.lower()
            found = [m for m in MONTHS if re.search(r"\b(in|during)\s+" + m + r"\b", sent)]
        return found[0] if len(found) == 1 else None

    def _period(self, ctx, it, ante) -> None:
        low = ctx.sentence.lower()
        for p in self.wb.periods:
            for ph in period_phrases(p):
                if contains_phrase(low, ph):
                    it.periods, it.period_how = [p], f"'{ph}' names {p}"
                    return
        if re.search(r"\bsince\s+(?:" + "|".join(MONTHS) + r")", low):
            it.periods, it.period_how = list(self.wb.periods), "cumulative (all periods to date)"
            return
        if any(contains_phrase(low, ph) for ph in self.cfg.period_previous) and self.wb.previous_period:
            it.periods, it.period_how = [self.wb.previous_period], f"points to {self.wb.previous_period}"
            return
        if ante and ante.periods:
            it.periods, it.period_how = ante.periods, "same as the figure before it"
            return
        it.periods, it.period_how = [self.wb.current_period], f"current period ({self.wb.current_period})"


def _q(period: str) -> int:
    m = re.search(r"q([1-4])", period.lower())
    return int(m.group(1)) if m else 0


def _quarter_of(month: str) -> int:
    return MONTHS.index(month) // 3 + 1

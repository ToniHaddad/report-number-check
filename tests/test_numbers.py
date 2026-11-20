import pytest

from numcheck.numbers import extract_claims


def claims(text, cfg, heading=False):
    return extract_claims(text, 0, cfg, is_heading=heading)


def one(text, cfg):
    cs = claims(text, cfg)
    assert len(cs) == 1, [c.text for c in cs]
    return cs[0]


@pytest.mark.parametrize("text,value,kind", [
    ("We reached 3,284 households.", 3284, "count"),
    ("We reached 412 households.", 412, "count"),
    ("A total of 1,204,500 meals were served.", 1204500, "count"),
    ("Attendance was 62% this quarter.", 62, "percent"),
    ("Attendance was 62 percent this quarter.", 62, "percent"),
    ("Attendance was 62 per cent this quarter.", 62, "percent"),
    ("Attendance was 62.5 percent this quarter.", 62.5, "percent"),
    ("We transferred USD 1,450 to each.", 1450, "money"),
    ("We transferred US$ 2,000 in total.", 2000, "money"),
])
def test_plain_numbers(text, value, kind, cfg):
    c = one(text, cfg)
    assert c.value == pytest.approx(value)
    assert c.kind == kind


def test_scaled_numbers_carry_their_rounding(cfg):
    c = one("Some 1.2 thousand people attended.", cfg)
    assert c.value == pytest.approx(1200)
    assert c.precision == pytest.approx(50)      # 1.2 thousand covers 1,150 to 1,250
    m = one("In total, USD 1.43 million was transferred.", cfg)
    assert m.kind == "money" and m.value == pytest.approx(1_430_000)
    assert m.precision == pytest.approx(5_000)
    assert m.text == "USD 1.43 million"


@pytest.mark.parametrize("text,value", [
    ("In Tripoli, twelve surveys were rescheduled.", 12),
    ("This quarter forty-two staff and volunteers were trained.", 42),
    ("Eighty-two teachers completed the course.", 82),
    ("The team reached one hundred and five households.", 105),
    ("They trained twenty-three of them women.", 23),
])
def test_spelled_numbers(text, value, cfg):
    c = one(text, cfg)
    assert c.value == value and c.spelled


@pytest.mark.parametrize("text,value,hedge", [
    ("nearly 3,000 households were assisted", 3000, "nearly"),
    ("almost 3,000 households were assisted", 3000, "nearly"),
    ("over 450 kits were handed out", 450, "over"),
    ("more than 450 kits were handed out", 450, "over"),
    ("about 3,000 households were assisted", 3000, "about"),
    ("an estimated 3,000 households were assisted", 3000, "about"),
    ("at least 20 schools were reached", 20, "at_least"),
    ("fewer than 50 complaints were received", 50, "under"),
    ("more than USD 2.8 million was transferred", 2_800_000, "over"),
])
def test_hedges(text, value, hedge, cfg):
    c = one(text, cfg)
    assert c.value == pytest.approx(value)
    assert c.hedge == hedge


@pytest.mark.parametrize("text,value,hedge", [
    ("about a third of households reported debt", 100 / 3, "about"),
    ("just over half of the people reached were women", 50, "over"),
    ("two thirds of the latrines were finished", 200 / 3, None),
    ("a quarter of the schools have water", 25, None),
])
def test_fractions(text, value, hedge, cfg):
    c = one(text, cfg)
    assert c.kind == "fraction"
    assert c.value == pytest.approx(value)
    assert c.hedge == hedge


@pytest.mark.parametrize("text", [
    "The report was submitted on 15 October 2026.",
    "Covering 1 July to 30 September 2026.",
    "Fuel shortages in August 2026 slowed transport.",
    "During the third quarter of 2026 the team worked hard.",
    "See Annex 2, page 14 for the procedure.",
    "As described in section 4.2 of the plan.",
    "Call the hotline on 81 234 567 for help.",
    "Or by WhatsApp on +961 3 456 789.",
    "The toll-free line 0800 721 316 is open daily.",
    "Grant reference NR-LB-2026-014.",
    "Cases must be closed within 14 days.",
    "Transport was stopped for nine days.",
    "Classes are for children aged 6 to 14.",
    "Each kit holds a 20-litre jerrycan.",
    "Version 1.2 of the report.",
    "Dates: 1/7/2026 to 30/9/2026.",
    "One of the main challenges was fuel.",
    "The basket for a family of five reached a new high.",
    "The first half of the year was dry.",
    "Shelters above 1,000 metres need winter kits.",
    "See the 4W matrix for details.",
])
def test_non_claims_are_ignored(text, cfg):
    assert claims(text, cfg) == []


def test_heading_numbering_is_ignored(cfg):
    assert claims("3.1 Output 1: Cash transfers delivered", cfg, heading=True) == []
    assert claims("1. Summary", cfg, heading=True) == []


def test_number_after_a_comma_following_a_month_is_still_a_claim(cfg):
    c = one("According to a survey published in July, 44 percent of households cut meals.", cfg)
    assert c.value == 44


def test_spans_cover_hedge_and_suffix(cfg):
    text = "The programme reached nearly 15,000 people."
    c = one(text, cfg)
    assert text[c.start:c.end] == "nearly 15,000"
    assert text[c.num_start:c.num_end] == "15,000"

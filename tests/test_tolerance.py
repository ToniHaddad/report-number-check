import pytest

from numcheck.checks import within
from numcheck.numbers import extract_claims


def claim(text, cfg):
    cs = extract_claims(text, 0, cfg)
    assert len(cs) == 1
    return cs[0]


@pytest.mark.parametrize("text,actual,ok", [
    # the example from the brief: "nearly 3,000" is consistent with 2,940 and not with 3,100
    ("nearly 3,000 households", 2940, True),
    ("nearly 3,000 households", 3100, False),
    ("nearly 3,000 households", 3000, True),
    ("nearly 3,000 households", 2700, False),      # too far below to be "nearly"
    ("over 450 kits", 470, True),
    ("over 450 kits", 450, False),                 # "over" must be strictly above
    ("over 450 kits", 431, False),                 # a hedge that overstates
    ("over 450 kits", 600, False),                 # far above: "over 450" understates badly
    ("about 3,000 households", 2900, True),
    ("about 3,000 households", 3140, True),
    ("about 3,000 households", 3200, False),
    ("at least 20 schools", 20, True),
    ("at least 20 schools", 19, False),
    ("fewer than 50 complaints", 49, True),
    ("fewer than 50 complaints", 50, False),
])
def test_hedge_tolerance(text, actual, ok, cfg):
    assert within(claim(text, cfg), actual, cfg)[0] is ok


@pytest.mark.parametrize("text,actual,ok", [
    ("3,284 households", 3284, True),
    ("3,284 households", 3285, False),            # an unhedged figure must match exactly
    ("1.2 thousand people", 1240, True),          # rounding implied by how it is written
    ("1.2 thousand people", 1260, False),
    ("USD 1.43 million", 1_434_999, True),
    ("USD 1.43 million", 1_436_000, False),
    ("62 percent", 62.4, True),
    ("62 percent", 62.6, False),
    ("62.5 percent", 62.54, True),
])
def test_rounding_tolerance(text, actual, ok, cfg):
    assert within(claim(text, cfg), actual, cfg)[0] is ok


@pytest.mark.parametrize("text,actual,ok", [
    ("about a third of households", 31.0, True),
    ("about a third of households", 40.0, False),
    ("just over half of the people", 52.0, True),
    ("just over half of the people", 49.0, False),
    ("two thirds of latrines", 65.0, True),
    ("two thirds of latrines", 60.0, False),
])
def test_fraction_tolerance(text, actual, ok, cfg):
    assert within(claim(text, cfg), actual, cfg)[0] is ok

"""WASH-2026: hygiene and winterisation, Baalbek, Hermel and Zahle. Synthetic; HELD OUT.

Written before the checker was changed for the stock-and-distribution scenario and never used
while tuning. Only scripts/benchmark.py --final runs on it.
"""
import random

from .engine import Indicator, Item, dispatch_rows, indicator_rows, stock_rows

SLUG = "wash-2026-q3"
SPLIT = "heldout"
PROJECT = "WASH-2026"
WORKBOOK_TITLE = "WASH-2026 Hygiene and winterisation, Q2 and Q3 2026"
LOC_HEADER = "District"
LOCATIONS = ["Baalbek", "Hermel", "Zahle"]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("W-1", "Households receiving family hygiene kits", "Households"),
    Indicator("W-2", "Individuals reached with hygiene items", "People", sex=True, age=True),
    Indicator("W-3", "Children receiving winter clothing kits", "Children", sex=True),
    Indicator("W-4", "Hygiene promotion sessions held", "Sessions"),
    Indicator("W-5", "Households receiving winterisation kits", "Households"),
]
ITEMS = [
    Item("HYG-KIT-001", "Family hygiene kit", 4),
    Item("HYG-SAN-003", "Sanitary pad pack", 24),
    Item("SHE-BLA-002", "Thermal blanket", 20),
    Item("NFI-WIN-004", "Child winter clothing kit", 8),
    Item("NFI-JER-001", "Water jerrycan 20 L", 12),
]
WH9, WH7 = "WH-09 Baalbek", "WH-07 Zahle"
SOCIAL = "Social department, Zahle centre"


def build(rng=None):
    rng = rng or random.Random(26)
    ind = {i.id: i for i in INDICATORS}
    items = {i.code: i for i in ITEMS}
    rows = []
    rows += indicator_rows(ind["W-1"], PERIODS, {"Baalbek": (900, 1100), "Hermel": (500, 650), "Zahle": (700, 800)},
                           rng, ach=(0.84, 0.98))
    rows += indicator_rows(ind["W-2"], PERIODS, {"Baalbek": (4300, 5200), "Hermel": (2400, 3100),
                                                 "Zahle": (3300, 3800)}, rng, ach=(0.84, 0.98))
    rows += indicator_rows(ind["W-3"], PERIODS, {"Baalbek": (200, 450), "Hermel": (250, 600), "Zahle": (150, 350)},
                           rng, ach=(0.8, 0.97), female=(0.47, 0.53))
    rows += indicator_rows(ind["W-4"], PERIODS, {"Baalbek": (30, 36), "Hermel": (20, 24), "Zahle": (24, 28)},
                           rng, ach=(0.8, 1.0))
    rows += indicator_rows(ind["W-5"], PERIODS, {"Baalbek": (150, 400), "Hermel": (200, 520), "Zahle": (100, 260)},
                           rng, ach=(0.8, 0.96))
    routes = [
        ("HYG-KIT-001", WH9, "Baalbek centre", "Centre", (80, 110)),
        ("HYG-KIT-001", WH9, "Hermel centre", "Centre", (45, 60)),
        ("HYG-KIT-001", WH7, "Zahle centre", "Centre", (55, 75)),
        ("HYG-SAN-003", WH9, "Baalbek centre", "Centre", (8, 14)),
        ("HYG-SAN-003", WH7, SOCIAL, "Department", (5, 9)),
        ("SHE-BLA-002", WH9, "Hermel centre", "Centre", (10, 25)),
        ("SHE-BLA-002", WH9, "Hermel Youth Club", "Partner", (5, 12)),
        ("SHE-BLA-002", WH7, "Zahle centre", "Centre", (6, 15)),
        ("NFI-WIN-004", WH9, "Hermel centre", "Centre", (10, 20)),
        ("NFI-WIN-004", WH7, "Zahle centre", "Centre", (6, 12)),
        ("NFI-JER-001", WH9, "Baalbek centre", "Centre", (4, 9)),
    ]
    drows = dispatch_rows(items, PERIODS, routes, rng, loose={("NFI-WIN-004", "Hermel centre")})
    srows = stock_rows(items, PERIODS, drows, rng, openings={(WH9, "SHE-BLA-002"): 0},
                       inkind={(WH9, "SHE-BLA-002")})
    return rows, drows, srows


D = "dispatch"
S = "stock"
CLAIMS = {
    # executive summary
    "hh_hyg_total": dict(ind="W-1"),
    "ppl_err": dict(ind="W-2", error=dict(type="households_as_people", ind="W-1")),
    "kits_dsp_total": dict(src=D, item="HYG-KIT-001"),
    "bla_inkind": dict(src=S, item="SHE-BLA-002", wh=WH9, measure="received_inkind"),
    # reach by district
    "hh_baalbek": dict(ind="W-1", loc="Baalbek"),
    "hh_hermel": dict(ind="W-1", loc="Hermel"),
    "hh_zahle": dict(ind="W-1", loc="Zahle"),
    "hh_total_err": dict(ind="W-1", error=dict(type="district_total", delta=40)),
    "ppl_total": dict(ind="W-2"),
    "ppl_f": dict(ind="W-2", sex="F"),
    "ppl_children": dict(ind="W-2", age="CH"),
    "ppl_older": dict(ind="W-2", age="OL"),
    "ppl_june": dict(ind="W-2", period="prev"),
    "children_winter": dict(ind="W-3"),
    "children_winter_girls": dict(ind="W-3", sex="F"),
    "sessions_err": dict(ind="W-4", error=dict(type="previous_quarter")),
    "hh_winter_hermel": dict(ind="W-5", loc="Hermel"),
    # distribution
    "kits_baalbek_boxes": dict(src=D, item="HYG-KIT-001", wh=WH9, dest="Baalbek centre", measure="boxes"),
    "bla_hermel_err": dict(src=D, item="SHE-BLA-002", dest="Hermel centre", measure="boxes",
                           error=dict(type="pieces_as_boxes")),
    "bla_youth_club": dict(src=D, item="SHE-BLA-002", dest="Hermel Youth Club"),
    "winter_hermel": dict(src=D, item="NFI-WIN-004", dest="Hermel centre", fmt="boxpcs"),
    "san_social_err": dict(src=D, item="HYG-SAN-003", dest=SOCIAL, error=dict(type="boxes_as_pieces")),
    "jer_err": dict(src=D, item="NFI-JER-001", error=dict(type="transposed")),
    "kits_aug": dict(src=D, item="HYG-KIT-001", month="Aug"),
    # stock
    "kits_opening": dict(src=S, item="HYG-KIT-001", wh=WH9, measure="opening"),
    "kits_received": dict(src=S, item="HYG-KIT-001", wh=WH9, measure="received"),
    "kits_dispatched": dict(src=S, item="HYG-KIT-001", wh=WH9, measure="dispatched"),
    "kits_balance_err": dict(src=S, item="HYG-KIT-001", wh=WH9, measure="closing",
                             error=dict(type="wrong_balance", delta=120)),
    "bla_balance": dict(src=S, item="SHE-BLA-002", wh=WH9, measure="closing"),
    # table 1
    "t_kit9_pcs": dict(src=D, item="HYG-KIT-001", wh=WH9),
    "t_kit9_box": dict(src=D, item="HYG-KIT-001", wh=WH9, measure="boxes"),
    "t_kit7_pcs": dict(src=D, item="HYG-KIT-001", wh=WH7),
    "t_kit7_box": dict(src=D, item="HYG-KIT-001", wh=WH7, measure="boxes"),
    "t_bla9_pcs": dict(src=D, item="SHE-BLA-002", wh=WH9),
    "t_bla9_box": dict(src=D, item="SHE-BLA-002", wh=WH9, measure="boxes"),
    "t_win7_pcs": dict(src=D, item="NFI-WIN-004", wh=WH7),
    "t_win7_box": dict(src=D, item="NFI-WIN-004", wh=WH7, measure="boxes"),
}

BLOCKS = [
    ("title", "Hygiene and Winterisation in Baalbek, Hermel and Zahle"),
    ("meta", "The Organization. Quarterly report to donors, project [[WASH-2026|code]], "
             "[[July to September 2026|period]]. Prepared by the programme and logistics teams on "
             "[[14 October 2026|date]]."),
    ("h1", "Executive summary"),
    ("p", "In the third quarter the Organization delivered family hygiene kits to {hh_hyg_total} households in "
          "Baalbek, Hermel and Zahle, which means the project reached {ppl_err} people with hygiene items. The "
          "warehouses sent out {kits_dsp_total} hygiene kits in total. Winter preparations started early in the "
          "high villages of Hermel, where nights are already cold in September, and a private donor gave "
          "{bla_inkind} thermal blankets in kind to the Baalbek warehouse."),
    ("p", "Figures in this report come from the project's indicator table and from the stock records kept in "
          "the warehouses: goods received notes for incoming stock and waybills for every dispatch. Quantities "
          "are counted in pieces; boxes are given where they help the reader."),
    ("h1", "Context"),
    ("p", "The Bekaa and Baalbek-Hermel governorates have some of the highest poverty rates in the country, and "
          "many families live in unfinished buildings, informal settlements or rented rooms without heating. "
          "Water supply is irregular in the summer, and households spend a growing share of their income on "
          "water trucking, soap and detergent. Prices for basic hygiene items rose again during the quarter, so "
          "many families stopped buying them altogether and relied on the kits."),
    ("p", "Winter arrives early in the upper villages of Hermel and in the mountain areas east of Baalbek. The "
          "project therefore splits its winter support into [[two|unverifiable]] rounds: thermal blankets and "
          "children's clothing are positioned in the warehouses and centres before the cold, and the main "
          "distribution follows once the household lists have been confirmed with the local committees."),
    ("h1", "Reach by district"),
    ("p", "Households receiving a family hygiene kit: Baalbek {hh_baalbek}, Hermel {hh_hermel}, Zahle "
          "{hh_zahle}, a total of {hh_total_err} households across the three districts."),
    ("p", "The kits reached {ppl_total} individuals, of whom {ppl_f} were women and girls. Children under "
          "[[18|age]] made up the largest group with {ppl_children} people, and {ppl_older} were older people "
          "aged [[60|age]] and above. At the end of June the count stood at {ppl_june} individuals, so reach "
          "grew as the Hermel distributions resumed."),
    ("p", "Winter clothing kits went to {children_winter} children, {children_winter_girls} of them girls. In "
          "Hermel, {hh_winter_hermel} households received a winterisation kit before the first frost. "
          "Community volunteers ran {sessions_err} hygiene promotion sessions in the three districts, mostly "
          "in the centres and in [[two|unverifiable]] informal settlements near Baalbek."),
    ("h1", "Distribution and stock"),
    ("p", "All hygiene and winter items left the warehouses on waybills, signed by the receiving centre or "
          "partner. From WH-[[09|code]] the Baalbek centre received {kits_baalbek_boxes} boxes of family "
          "hygiene kits over the quarter. The Hermel centre took {bla_hermel_err} boxes of thermal blankets, "
          "and the Hermel Youth Club, a partner organization, collected {bla_youth_club} thermal blankets "
          "for families in the upper villages."),
    ("p", "Child winter clothing kits for Hermel were dispatched as {winter_hermel}, because the last "
          "deliveries were split to match the lists of children registered at the centre. The Social "
          "department of the Zahle centre received {san_social_err} sanitary pad packs for women in its "
          "case management programme. A total of {jer_err} water jerrycans went to the Baalbek centre for "
          "families with no safe water storage. Dispatches of hygiene kits peaked in August, when "
          "{kits_aug} kits left the warehouses."),
    ("p", "Table [[1|section]] gives the quarter's dispatches for the main items, by warehouse."),
    ("table", {
        "headers": ["Item", "Warehouse", "Pieces dispatched", "Boxes"],
        "rows": [
            ["Family hygiene kit", "WH-[[09|code]] Baalbek", "{t_kit9_pcs}", "{t_kit9_box}"],
            ["Family hygiene kit", "WH-[[07|code]] Zahle", "{t_kit7_pcs}", "{t_kit7_box}"],
            ["Thermal blanket", "WH-[[09|code]] Baalbek", "{t_bla9_pcs}", "{t_bla9_box}"],
            ["Child winter clothing kit", "WH-[[07|code]] Zahle", "{t_win7_pcs}", "{t_win7_box}"],
        ],
    }),
    ("p", "At WH-[[09|code]] Baalbek the quarter opened with {kits_opening} family hygiene kits in stock. The "
          "warehouse received {kits_received} kits and dispatched {kits_dispatched}, leaving a balance of "
          "{kits_balance_err} kits on [[30 September|date]]. The thermal blanket balance in the same warehouse "
          "was {bla_balance} pieces, most of it from the in-kind donation, which will cover the first winter "
          "round in [[November|date]]."),
    ("h1", "Accountability to communities"),
    ("p", "Families can call the free hotline on [[01 555 210|phone]] or speak to the help desk at each "
          "centre. Most calls this quarter asked when winter items would arrive and whether households "
          "registered after the summer could still be included. Complaints about missing items in [[three|unverifiable]] "
          "kits were traced to a packing error at the supplier, and the kits were replaced within a week."),
    ("h1", "Constraints"),
    ("p", "Road access to the upper villages of Hermel was cut for [[four days|duration]] in [[September|date]] "
          "after heavy rain, which delayed [[two|unverifiable]] planned distributions. Fuel costs for the "
          "trucks rose again, and the logistics team grouped dispatches so that each truck served several "
          "centres on one trip. One delivery of jerrycans arrived with damaged handles; a damage report was "
          "written and the operations manager approved the write-off."),
    ("p", "The project keeps its stock separate from the other projects that share the Baalbek warehouse. "
          "Every receipt and dispatch is recorded against the project code, so that donor-funded kits are never "
          "counted twice or used for another project."),
    ("h1", "Monitoring"),
    ("p", "Centre staff record each household and its members when a kit is handed over, using the same "
          "household number as in the registration list. The monitoring officer checks these lists against "
          "the waybills each month, before the figures are entered in the indicator table. A phone survey of "
          "a sample of families will be carried out after the first winter round to check whether the "
          "blankets and clothing reached the people who needed them most."),
    ("h1", "Coordination"),
    ("p", "The project shares its distribution plans with the local authorities and with the other "
          "organizations working in the same villages, so that families are not left out and no household "
          "receives the same kit twice. Lists of households receiving winter items were exchanged with the "
          "Hermel Youth Club before each distribution, and the club's volunteers helped reach older people who "
          "could not travel to the centre."),
    ("h1", "Lessons learned"),
    ("p", "Packing kits for each family at the warehouse saved time at the centres but made it harder to adjust "
          "the contents for large households. From the next round, centres will add extra soap and sanitary "
          "items on the spot, recorded on the same waybill. The team also learned that dispatching in full boxes "
          "simplifies the stock count, while splitting boxes at the last delivery avoids leaving a few pieces "
          "stranded in a centre that cannot use them."),
    ("p", "Finally, monthly checks of the stock records against the dispatch summary caught [[two|unverifiable]] "
          "waybills entered under the wrong project code. Both were corrected before the figures in this report "
          "were finalised, and the warehouse keepers received a short refresher on choosing the project when "
          "they record a dispatch."),
    ("h1", "Outlook"),
    ("p", "In the fourth quarter the project will distribute winterisation kits in Baalbek and Zahle, and "
          "plans to reach [[1,500|unverifiable]] more households before the end of December, subject to "
          "funding. Thermal blankets already in stock will go first to older people living alone and to "
          "families in unfinished buildings."),
    ("meta", "Synthetic report for testing. All names, figures and codes are invented."),
]

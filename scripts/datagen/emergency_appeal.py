"""EA-2026: emergency appeal for people displaced into collective shelters. Synthetic; used for tuning."""
import random

from .engine import Indicator, Item, dispatch_rows, indicator_rows, stock_rows

SLUG = "ea-2026-q3"
SPLIT = "tuning"
PROJECT = "EA-2026"
WORKBOOK_TITLE = "EA-2026 Emergency appeal, collective shelters, Q2 and Q3 2026"
LOC_HEADER = "Shelter"
SPS, STI, JPS, JSS = "Saida Public School", "Saida Technical Institute", "Jbeil Public School", "Jounieh Secondary School"
LOCATIONS = [SPS, STI, JPS, JSS]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("EA-1", "People in collective shelters receiving relief items", "People", sex=True, age=True),
    Indicator("EA-2", "Households in collective shelters receiving relief items", "Households"),
    Indicator("EA-3", "Hot meals served in collective shelters", "Meals"),
]
ITEMS = [
    Item("SHE-MAT-001", "Foam mattress", 10),
    Item("SHE-BLA-001", "Fleece blanket", 20),
    Item("HYG-KIT-001", "Family hygiene kit", 4),
    Item("HYG-DIA-002", "Baby diaper pack", 6),
]
WH14, WH21 = "WH-14 Saida", "WH-21 Jbeil"
MEDICAL = "Medical department, Saida centre"


def build(rng=None):
    rng = rng or random.Random(612)
    ind = {i.id: i for i in INDICATORS}
    items = {i.code: i for i in ITEMS}
    rows = []
    rows += indicator_rows(ind["EA-1"], PERIODS, {SPS: (400, 1400), STI: (300, 1100), JPS: (250, 900),
                                                  JSS: (200, 750)}, rng, ach=(0.86, 0.98), female=(0.5, 0.54))
    rows += indicator_rows(ind["EA-2"], PERIODS, {SPS: (90, 310), STI: (70, 240), JPS: (55, 200), JSS: (45, 165)},
                           rng, ach=(0.86, 0.98))
    rows += indicator_rows(ind["EA-3"], PERIODS, {SPS: (9000, 36000), STI: (7000, 28000), JPS: (6000, 23000),
                                                  JSS: (5000, 19000)}, rng, ach=(0.86, 0.98))
    routes = [
        ("SHE-MAT-001", WH14, SPS, "Shelter", (8, 15)),
        ("SHE-MAT-001", WH14, STI, "Shelter", (6, 12)),
        ("SHE-MAT-001", WH21, JPS, "Shelter", (5, 10)),
        ("SHE-MAT-001", WH21, JSS, "Shelter", (4, 9)),
        ("SHE-BLA-001", WH14, SPS, "Shelter", (5, 9)),
        ("SHE-BLA-001", WH14, STI, "Shelter", (4, 8)),
        ("SHE-BLA-001", WH21, JPS, "Shelter", (3, 6)),
        ("SHE-BLA-001", WH21, JSS, "Shelter", (3, 6)),
        ("HYG-KIT-001", WH14, SPS, "Shelter", (40, 60)),
        ("HYG-KIT-001", WH14, STI, "Shelter", (30, 50)),
        ("HYG-KIT-001", WH21, JPS, "Shelter", (25, 40)),
        ("HYG-KIT-001", WH21, JSS, "Shelter", (20, 35)),
        ("HYG-DIA-002", WH14, MEDICAL, "Department", (20, 35)),
    ]
    drows = dispatch_rows(items, PERIODS, routes, rng, loose={("HYG-KIT-001", JSS)})
    srows = stock_rows(items, PERIODS, drows, rng, openings={},
                       inkind={(WH14, "SHE-MAT-001"), (WH21, "SHE-BLA-001")})
    return rows, drows, srows


D = "dispatch"
S = "stock"
CLAIMS = {
    # summary
    "ppl_total": dict(ind="EA-1"),
    "hh_total": dict(ind="EA-2"),
    "mats_total": dict(src=D, item="SHE-MAT-001"),
    "kits_about": dict(src=D, item="HYG-KIT-001", fmt="about"),
    # shelters
    "hh_sps": dict(ind="EA-2", loc=SPS),
    "hh_sti": dict(ind="EA-2", loc=STI),
    "hh_jps": dict(ind="EA-2", loc=JPS),
    "hh_jss": dict(ind="EA-2", loc=JSS),
    "hh_total2": dict(ind="EA-2"),
    "ppl_jps_err": dict(ind="EA-1", loc=JPS, error=dict(type="households_as_people", ind="EA-2")),
    "ppl_sti": dict(ind="EA-1", loc=STI),
    "ppl_sti_f": dict(ind="EA-1", loc=STI, sex="F"),
    "ppl_sti_m_err": dict(ind="EA-1", loc=STI, sex="M", error=dict(type="split_sum", delta=50)),
    "ppl_older": dict(ind="EA-1", age="OL"),
    "ppl_children_share": dict(ind="EA-1", age="CH", fmt="word_children"),
    "meals_err": dict(ind="EA-3", error=dict(type="transposed")),
    "meals_june": dict(ind="EA-3", period="prev"),
    # table
    **{f"t_{k}_{m}": dict(ind="EA-1", loc=loc, **q)
       for k, loc in (("sps", SPS), ("sti", STI), ("jps", JPS), ("jss", JSS))
       for m, q in (("f", {"sex": "F"}), ("m", {"sex": "M"}), ("ch", {"age": "CH"}), ("tot", {}))},
    # dispatch
    "mats_sps_boxes": dict(src=D, item="SHE-MAT-001", dest=SPS, measure="boxes"),
    "mats_jps_err": dict(src=D, item="SHE-MAT-001", dest=JPS, error=dict(type="boxes_as_pieces")),
    "bla_jss": dict(src=D, item="SHE-BLA-001", dest=JSS),
    "kits_jss": dict(src=D, item="HYG-KIT-001", dest=JSS, fmt="boxpcs"),
    "diapers_medical": dict(src=D, item="HYG-DIA-002", dest=MEDICAL),
    "kits_jps_err": dict(src=D, item="HYG-KIT-001", dest=JPS, error=dict(type="previous_quarter")),
    "bla_aug": dict(src=D, item="SHE-BLA-001", month="Aug"),
    # stock
    "mats_inkind": dict(src=S, item="SHE-MAT-001", wh=WH14, measure="received_inkind"),
    "mats_wh14_balance": dict(src=S, item="SHE-MAT-001", wh=WH14, measure="closing"),
    "bla21_opening": dict(src=S, item="SHE-BLA-001", wh=WH21, measure="opening"),
    "bla21_received": dict(src=S, item="SHE-BLA-001", wh=WH21, measure="received"),
    "bla21_dispatched": dict(src=S, item="SHE-BLA-001", wh=WH21, measure="dispatched"),
    "bla21_balance_err": dict(src=S, item="SHE-BLA-001", wh=WH21, measure="closing",
                              error=dict(type="wrong_balance", delta=40)),
}
CLAIMS["t_jss_tot"] = dict(ind="EA-1", loc=JSS, error=dict(type="district_total", delta=30))
del CLAIMS["ppl_children_share"]

BLOCKS = [
    ("title", "Emergency Appeal: Relief Items for Displaced Families in Collective Shelters"),
    ("meta", "The Organization. Quarterly report to donors, project [[EA-2026|code]], third quarter "
             "[[2026|year]]. Covers [[1 July|date]] to [[30 September 2026|date]]."),
    ("h1", "[[1|section]]. Summary"),
    ("p", "Since the displacement began in [[June|date]], families have been staying in schools that the "
          "authorities opened as collective shelters in Saida, Jbeil and Jounieh. This quarter the Organization "
          "supplied relief items to {ppl_total} people in {hh_total} households across the [[four|unverifiable]] "
          "shelters it supports. The warehouses dispatched {mats_total} foam mattresses and about {kits_about} "
          "family hygiene kits to the shelters."),
    ("p", "Figures come from the project's indicator table and from the stock records of the Saida and Jbeil "
          "warehouses: goods received notes, including in-kind donations, and the waybills of every dispatch. "
          "Quantities are in pieces unless boxes or bales are mentioned."),
    ("h1", "[[2|section]]. Situation"),
    ("p", "Families arrived with very little and many had to leave again when access to their villages changed. "
          "Shelter committees, made up of volunteers from among the displaced families, keep the list of "
          "households in each school and tell the emergency operations room what is missing. The operations "
          "room decides which warehouse dispatches, follows each delivery until the shelter confirms it, and "
          "records cancelled deliveries when a road is closed."),
    ("p", "Schools are crowded, with several families sharing each classroom. Water and toilets are the main "
          "concern of the shelter committees, followed by mattresses and blankets for families who sleep on the "
          "floor, and hygiene items for women, babies and older people."),
    ("h1", "[[3|section]]. People reached in the shelters"),
    ("p", "Households supplied this quarter, by shelter: {hh_sps} at Saida Public School, {hh_sti} at Saida "
          "Technical Institute, {hh_jps} at Jbeil Public School and {hh_jss} at Jounieh Secondary School, "
          "{hh_total2} households in all."),
    ("p", "At Jbeil Public School the team reached {ppl_jps_err} people. Saida Technical Institute hosted "
          "{ppl_sti} people: {ppl_sti_f} women and girls and {ppl_sti_m_err} men and boys. Across the shelters, "
          "{ppl_older} older people received relief items, many of them with chronic illnesses that the "
          "Medical department follows up."),
    ("p", "Table [[1|section]] shows the people reached in each shelter, by sex and for children."),
    ("table", {
        "headers": ["Shelter", "Women and girls", "Men and boys", "Children", "Total"],
        "rows": [
            [SPS, "{t_sps_f}", "{t_sps_m}", "{t_sps_ch}", "{t_sps_tot}"],
            [STI, "{t_sti_f}", "{t_sti_m}", "{t_sti_ch}", "{t_sti_tot}"],
            [JPS, "{t_jps_f}", "{t_jps_m}", "{t_jps_ch}", "{t_jps_tot}"],
            [JSS, "{t_jss_f}", "{t_jss_m}", "{t_jss_ch}", "{t_jss_tot}"],
        ],
    }),
    ("p", "Volunteers in the shelter kitchens served {meals_err} hot meals during the quarter. By the end of "
          "June, when the shelters had just opened, {meals_june} meals had been served."),
    ("h1", "[[4|section]]. Relief items dispatched"),
    ("p", "Saida Public School received {mats_sps_boxes} bales of foam mattresses from WH-[[14|code]], "
          "and Jbeil Public School received {mats_jps_err} foam mattresses from WH-[[21|code]]. Jounieh "
          "Secondary School received {bla_jss} fleece blankets and {kits_jss} of family hygiene kits. Jbeil "
          "Public School received {kits_jps_err} family hygiene kits. The Medical department of the Saida "
          "centre received {diapers_medical} baby diaper packs for mothers of newborns seen at its clinic. "
          "Blanket dispatches peaked in August, when {bla_aug} blankets left the warehouses."),
    ("h1", "[[5|section]]. Stock and in-kind donations"),
    ("p", "A private company donated {mats_inkind} foam mattresses in kind to WH-[[14|code]] Saida, recorded "
          "on a goods received note with the donor's name and an estimated value. After the quarter's "
          "dispatches, WH-[[14|code]] held {mats_wh14_balance} mattresses."),
    ("p", "At WH-[[21|code]] Jbeil, the fleece blanket stock opened the quarter at {bla21_opening} pieces. The "
          "warehouse received {bla21_received} blankets, partly as in-kind donations, and dispatched "
          "{bla21_dispatched}, leaving {bla21_balance_err} in stock at the end of September."),
    ("p", "The appeal's stock is held separately from the other projects in the same warehouses. Donated items "
          "are recorded under the appeal's project code with the donor's name, so that each donor can be told "
          "where its goods went."),
    ("h1", "[[6|section]]. Protection and inclusion"),
    ("p", "Relief items are handed to each household in the presence of a shelter committee member, and the "
          "distribution list is read aloud so that families can see who has received what. Women, older people "
          "and people with disabilities are served first, and items for families who cannot queue are brought to "
          "their classroom. Separate distribution times were set for hygiene items for women and girls, with "
          "female volunteers handing them out."),
    ("p", "The Medical department visits each shelter weekly. It identifies pregnant women, newborns and people "
          "with chronic illnesses, and asks the operations room for diapers, hygiene items or extra blankets "
          "when they are needed. These requests are dispatched from the Saida centre's stock on a separate "
          "waybill so that they can be followed up."),
    ("h1", "[[7|section]]. Coordination"),
    ("p", "The emergency operations room met by phone every morning and kept a running chat with the shelter "
          "focal points, the warehouse keepers in Saida and Jbeil, and the drivers. Each request from a shelter "
          "was logged with the item, the quantity and the warehouse expected to send it. When access to Jounieh "
          "was restricted for [[two days|duration]] in [[August|date]], [[three|unverifiable]] planned "
          "deliveries were cancelled and rescheduled."),
    ("h1", "[[8|section]]. Accountability"),
    ("p", "Shelter committees collect complaints and suggestions every evening, and families can also call the "
          "hotline on [[01 555 902|phone]]. Most requests asked for more mattresses for families who arrived "
          "late, for baby formula and for clothes. Requests outside the appeal's scope were referred to other "
          "organizations working in the same shelters."),
    ("h1", "[[9|section]]. Challenges and lessons"),
    ("p", "The first deliveries were counted in bales and boxes at the warehouse but in pieces at the shelters, "
          "which led to confusion when shelters confirmed receipt. The waybill now shows both, and shelter "
          "focal points count pieces. Damaged mattresses from [[one|word]] delivery were recorded on a damage "
          "report and written off after approval by the operations manager."),
    ("p", "Keeping in-kind donations on the same stock records as purchased items made it possible to report "
          "to each donor without a separate spreadsheet. The team will keep this approach for the rest of the "
          "appeal."),
    ("h1", "[[10|section]]. Next steps"),
    ("p", "As some families return home, the appeal will shift from bulk relief items to return kits. The "
          "operations room expects to close [[one|word]] shelter in [[October|date]] and will move its remaining "
          "stock to the Saida warehouse."),
    ("meta", "Synthetic report for testing. All names, figures and codes are invented."),
]

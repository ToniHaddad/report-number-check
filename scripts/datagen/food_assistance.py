"""FA-2026: food assistance, Tripoli, Akkar, Zahle and Saida. Synthetic; used for tuning."""
import random

from .engine import Indicator, Item, dispatch_rows, indicator_rows, stock_rows

SLUG = "fa-2026-q3"
SPLIT = "tuning"
PROJECT = "FA-2026"
WORKBOOK_TITLE = "FA-2026 Food assistance, Q2 and Q3 2026"
LOC_HEADER = "District"
LOCATIONS = ["Tripoli", "Akkar", "Zahle", "Saida"]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("FA-1", "Households receiving monthly food parcels", "Households"),
    Indicator("FA-2", "Individuals in households receiving food parcels", "People", sex=True),
    Indicator("FA-3", "Food parcels distributed to households", "Parcels"),
    Indicator("FA-4", "Partner organizations supplied with food items", "Partners"),
]
ITEMS = [
    Item("FOO-PAR-001", "Family food parcel", 1),
    Item("FOO-RIC-001", "Rice 5 kg bag", 4),
    Item("FOO-CHE-002", "Canned cheese 200 g", 24),
    Item("FOO-OIL-001", "Sunflower oil 1 L", 12),
    Item("FOO-LEN-001", "Lentils 1 kg", 10),
]
WH3, WH11, WH7, WH14 = "WH-03 Tripoli", "WH-11 Halba", "WH-07 Zahle", "WH-14 Saida"
SOCIAL = "Social department, Tripoli centre"


def build(rng=None):
    rng = rng or random.Random(2026)
    ind = {i.id: i for i in INDICATORS}
    items = {i.code: i for i in ITEMS}
    rows = []
    rows += indicator_rows(ind["FA-1"], PERIODS, {"Tripoli": (1200, 1300), "Akkar": (800, 900),
                                                  "Zahle": (900, 1000), "Saida": (650, 700)}, rng, ach=(0.86, 0.98))
    rows += indicator_rows(ind["FA-2"], PERIODS, {"Tripoli": (5600, 6100), "Akkar": (3900, 4400),
                                                  "Zahle": (4200, 4700), "Saida": (3000, 3300)}, rng,
                           ach=(0.86, 0.98), female=(0.505, 0.53))
    rows += indicator_rows(ind["FA-3"], PERIODS, {"Tripoli": (3600, 3900), "Akkar": (2400, 2700),
                                                  "Zahle": (2700, 3000), "Saida": (1950, 2100)}, rng,
                           ach=(0.86, 0.98))
    rows += indicator_rows(ind["FA-4"], PERIODS, {"Tripoli": (2, 2), "Akkar": (1, 1), "Zahle": (1, 1),
                                                  "Saida": (1, 2)}, rng, ach=(1.0, 1.0))
    routes = [
        ("FOO-PAR-001", WH3, "Tripoli centre", "Centre", (1180, 1300)),
        ("FOO-PAR-001", WH11, "Halba centre", "Centre", (800, 900)),
        ("FOO-PAR-001", WH7, "Zahle centre", "Centre", (900, 1000)),
        ("FOO-PAR-001", WH14, "Saida centre", "Centre", (650, 700)),
        ("FOO-CHE-002", WH3, "Tripoli centre", "Centre", (20, 30)),
        ("FOO-CHE-002", WH3, "Cedar Hands Association", "Partner", (8, 14)),
        ("FOO-CHE-002", WH14, "Saida Family Kitchen", "Partner", (6, 10)),
        ("FOO-RIC-001", WH7, "Zahle centre", "Centre", (40, 60)),
        ("FOO-RIC-001", WH14, "Saida Family Kitchen", "Partner", (15, 25)),
        ("FOO-OIL-001", WH3, "Tripoli centre", "Centre", (15, 25)),
        ("FOO-OIL-001", WH11, "Halba centre", "Centre", (10, 18)),
        ("FOO-LEN-001", WH11, "Halba centre", "Centre", (8, 15)),
        ("FOO-LEN-001", WH3, SOCIAL, "Department", (3, 6)),
    ]
    drows = dispatch_rows(items, PERIODS, routes, rng, loose={("FOO-CHE-002", "Cedar Hands Association")})
    srows = stock_rows(items, PERIODS, drows, rng, openings={(WH3, "FOO-OIL-001"): 240},
                       inkind={(WH14, "FOO-RIC-001")})
    return rows, drows, srows


D = "dispatch"
S = "stock"
CLAIMS = {
    # summary
    "hh_total": dict(ind="FA-1"),
    "hh_pct": dict(ind="FA-1", measure="pct_target", fmt="pct"),
    "ppl_err": dict(ind="FA-2", error=dict(type="households_as_people", ind="FA-1")),
    "parcels_dsp_total": dict(src=D, item="FOO-PAR-001"),
    "partners": dict(ind="FA-4", fmt="word"),
    # results by district
    "hh_tripoli": dict(ind="FA-1", loc="Tripoli"),
    "hh_akkar": dict(ind="FA-1", loc="Akkar"),
    "hh_zahle": dict(ind="FA-1", loc="Zahle"),
    "hh_saida": dict(ind="FA-1", loc="Saida"),
    "hh_total_err": dict(ind="FA-1", error=dict(type="district_total", delta=-60)),
    "hh_june": dict(ind="FA-1", period="prev"),
    "ppl_total": dict(ind="FA-2"),
    "ppl_f": dict(ind="FA-2", sex="F"),
    "ppl_m_err": dict(ind="FA-2", sex="M", error=dict(type="split_sum", delta=100)),
    "ppl_nearly": dict(ind="FA-2", loc="Tripoli", fmt="nearly"),
    "parcels_dist": dict(ind="FA-3"),
    "parcels_cum_err": dict(ind="FA-3", period="cum", error=dict(type="hedge_overstates")),
    # warehouses
    "parcels_saida_err": dict(src=D, item="FOO-PAR-001", dest="Saida centre", error=dict(type="transposed")),
    "cheese_tripoli_err": dict(src=D, item="FOO-CHE-002", dest="Tripoli centre", measure="boxes",
                               error=dict(type="pieces_as_boxes")),
    "cheese_cedar": dict(src=D, item="FOO-CHE-002", dest="Cedar Hands Association", fmt="boxpcs"),
    "rice_zahle_boxes": dict(src=D, item="FOO-RIC-001", dest="Zahle centre", measure="boxes"),
    "oil_halba": dict(src=D, item="FOO-OIL-001", dest="Halba centre"),
    "lentils_social": dict(src=D, item="FOO-LEN-001", dest=SOCIAL),
    "cheese_sep": dict(src=D, item="FOO-CHE-002", month="Sep"),
    "parcels_q2": dict(src=D, item="FOO-PAR-001", period="prev"),
    # stock
    "oil_opening": dict(src=S, item="FOO-OIL-001", wh=WH3, measure="opening"),
    "oil_received": dict(src=S, item="FOO-OIL-001", wh=WH3, measure="received"),
    "oil_dispatched": dict(src=S, item="FOO-OIL-001", wh=WH3, measure="dispatched"),
    "oil_balance_err": dict(src=S, item="FOO-OIL-001", wh=WH3, measure="closing",
                            error=dict(type="wrong_balance", delta=-60)),
    "rice_inkind": dict(src=S, item="FOO-RIC-001", wh=WH14, measure="received_inkind"),
    "rice_balance": dict(src=S, item="FOO-RIC-001", wh=WH14, measure="closing"),
    # table
    "t_par_tri_pcs": dict(src=D, item="FOO-PAR-001", dest="Tripoli centre"),
    "t_oil_hal_pcs": dict(src=D, item="FOO-OIL-001", dest="Halba centre"),
    "t_oil_hal_box": dict(src=D, item="FOO-OIL-001", dest="Halba centre", measure="boxes"),
    "t_che_sfk_pcs": dict(src=D, item="FOO-CHE-002", dest="Saida Family Kitchen"),
    "t_che_sfk_box": dict(src=D, item="FOO-CHE-002", dest="Saida Family Kitchen", measure="boxes"),
    "t_ric_sfk_pcs": dict(src=D, item="FOO-RIC-001", dest="Saida Family Kitchen"),
    "t_ric_sfk_box": dict(src=D, item="FOO-RIC-001", dest="Saida Family Kitchen", measure="boxes"),
}

BLOCKS = [
    ("title", "Food Assistance for Vulnerable Households in North Lebanon, the Bekaa and the South"),
    ("meta", "The Organization. Quarterly narrative report, project [[FA-2026|code]]. Reporting period "
             "[[1 July|date]] to [[30 September 2026|date]]. Submitted on [[12 October 2026|date]]."),
    ("h1", "[[1|section]]. Summary"),
    ("p", "During the third quarter of [[2026|year]], the Organization delivered monthly food parcels to "
          "{hh_total} households in Tripoli, Akkar, Zahle and Saida, reaching {hh_pct} of the quarterly target. "
          "In total the project supported {ppl_err} people. The warehouses dispatched {parcels_dsp_total} family "
          "food parcels to the centres, and {partners} partner organizations received food items for their own "
          "kitchens and distributions."),
    ("p", "All figures in this report come from the project's indicator table and from the stock records: goods "
          "received notes for incoming stock, waybills for every dispatch and the stock card of each item in each "
          "warehouse. Quantities are counted in pieces, with boxes given where staff ordered in full boxes."),
    ("h1", "[[2|section]]. Context"),
    ("p", "Food prices continued to rise over the summer, and families in the programme areas told centre staff "
          "that they were skipping meals or buying food on credit. Daily work in construction and agriculture "
          "fell during the hottest months, and many households now depend on the monthly parcel as their main "
          "source of staple food. The Organization continued to select households with the social workers at "
          "each centre, using home visits to confirm the situation of new families."),
    ("p", "The food parcel was kept the same as in the previous quarter: rice, lentils, bulgur, sugar, oil, "
          "canned food and tea, packed for a family of [[five|word]] for one month. Larger families receive "
          "complementary items from the centre stock, recorded on a separate waybill."),
    ("h1", "[[3|section]]. Results by district"),
    ("p", "Households receiving monthly food parcels this quarter: Tripoli {hh_tripoli}, Akkar {hh_akkar}, "
          "Zahle {hh_zahle} and Saida {hh_saida}, for a total of {hh_total_err} households. At the end of June "
          "the project was supporting {hh_june} households, and the increase came mostly from new families "
          "referred by the social workers in Akkar."),
    ("p", "These households include {ppl_total} individuals: {ppl_f} women and girls and {ppl_m_err} men and "
          "boys. In Tripoli alone, the parcels fed nearly {ppl_nearly} people. Centres handed out {parcels_dist} "
          "food parcels to households over the quarter, and since April more than {parcels_cum_err} parcels have "
          "been distributed."),
    ("h1", "[[4|section]]. Dispatches from the warehouses"),
    ("p", "Every dispatch leaves a warehouse on a waybill signed by the receiving centre, department or partner. "
          "The Saida centre received {parcels_saida_err} family food parcels from WH-[[14|code]]. From "
          "WH-[[03|code]], the Tripoli centre received {cheese_tripoli_err} boxes of canned cheese for families "
          "with young children, and the Cedar Hands Association, a partner that runs a community kitchen, "
          "received {cheese_cedar} of canned cheese."),
    ("p", "The Zahle centre received {rice_zahle_boxes} boxes of rice in [[5 kg|measure]] bags. The Halba centre received "
          "{oil_halba} bottles of sunflower oil, and the Social department of the Tripoli centre received "
          "{lentils_social} bags of lentils for its emergency cases. Canned cheese dispatches were highest in "
          "September, with {cheese_sep} pieces. For comparison, the warehouses dispatched {parcels_q2} food "
          "parcels in the second quarter."),
    ("p", "Table [[1|section]] shows the dispatches to the main destinations for the quarter."),
    ("table", {
        "headers": ["Destination", "Item", "Pieces dispatched", "Boxes"],
        "rows": [
            ["Tripoli centre", "Family food parcel", "{t_par_tri_pcs}", "[[n/a|word]]"],
            ["Halba centre", "Sunflower oil", "{t_oil_hal_pcs}", "{t_oil_hal_box}"],
            ["Saida Family Kitchen", "Canned cheese", "{t_che_sfk_pcs}", "{t_che_sfk_box}"],
            ["Saida Family Kitchen", "Rice", "{t_ric_sfk_pcs}", "{t_ric_sfk_box}"],
        ],
    }),
    ("h1", "[[5|section]]. Stock position"),
    ("p", "At WH-[[03|code]] Tripoli the quarter opened with {oil_opening} bottles of sunflower oil. The "
          "warehouse received {oil_received} bottles, dispatched {oil_dispatched} and closed the quarter with a "
          "balance of {oil_balance_err} bottles. At WH-[[14|code]] Saida, a local supermarket chain donated "
          "{rice_inkind} bags of rice in kind, recorded on a goods received note with the donor's name, and the "
          "rice balance at the end of September was {rice_balance} bags."),
    ("p", "Stock for this project is kept apart from the other projects that share the same warehouses. Each "
          "balance is held per warehouse, per project, per item and per expiry date, and items are dispatched "
          "first expired, first out. No balance went below zero during the quarter."),
    ("h1", "[[6|section]]. Partners and departments"),
    ("p", "Partner organizations receive food items on the same waybills as the centres and confirm each "
          "delivery with a signature and a stamp. The Cedar Hands Association runs a community kitchen in "
          "Tripoli that serves older people living alone, and the Saida Family Kitchen prepares hot meals for "
          "families in [[two|unverifiable]] neighbourhoods near the old city. Both partners report the number of "
          "meals served each month, which the programme team checks against the quantities dispatched."),
    ("p", "The Social department of the Tripoli centre holds a small reserve of lentils, rice and oil for "
          "families in crisis who cannot wait for the next monthly distribution. Each item taken from this "
          "reserve is recorded against the family's case number, so that the department can show which "
          "households were helped and why."),
    ("h1", "[[7|section]]. Monitoring"),
    ("p", "Centre staff record each parcel handed over against the household number from the registration "
          "list. The monitoring officer compares these lists with the waybills every month and follows up any "
          "difference with the centre manager before the figures are entered in the indicator table. A phone "
          "survey of a sample of households after each distribution round asks whether the parcel lasted the "
          "month and which items families ran out of first."),
    ("h1", "[[8|section]]. Accountability to affected people"),
    ("p", "Families can reach the Organization through the hotline on [[01 555 384|phone]] or at the help desk "
          "of each centre. Most calls this quarter asked about the distribution date or about adding a new "
          "family member to the household record. [[Three|unverifiable]] complaints concerned the quality of "
          "the bulgur in one batch; the batch was withdrawn and replaced, and the supplier was informed."),
    ("h1", "[[9|section]]. Challenges"),
    ("p", "A delayed purchase order in [[August|date]] left the Halba centre short of lentils for "
          "[[nine days|duration]], so the centre gave a second bag of rice instead. Fuel prices raised the cost "
          "of each truck trip, and the logistics team combined dispatches to the Tripoli centre and to the Cedar "
          "Hands Association on the same day. [[Two|unverifiable]] cartons of oil were damaged in transit; a "
          "damage report was written and the operations manager approved the write-off."),
    ("h1", "[[10|section]]. Lessons learned"),
    ("p", "Recording boxes and pieces separately on the waybill reduced errors at the centres, because staff "
          "could check a delivery against the waybill without opening every box. Monthly reconciliation of the "
          "stock card with the dispatch summary caught [[two|unverifiable]] waybills recorded under the wrong project before the "
          "figures were reported."),
    ("p", "The team also found that partners prefer fewer, larger deliveries, while centres prefer weekly "
          "deliveries that match their distribution days. From the next quarter the logistics team will plan "
          "the [[two|unverifiable]] kinds of destination separately."),
    ("h1", "[[11|section]]. Plans for the next quarter"),
    ("p", "In the fourth quarter the project plans to reach [[3,800|unverifiable]] households per month, subject "
          "to funding, and will add winter items to the parcel for families in Akkar and Zahle. A review of the "
          "parcel contents with the centres is planned for [[November 2026|date]]."),
    ("meta", "Synthetic report for testing. All names, figures and codes are invented."),
]

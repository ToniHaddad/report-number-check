"""Kenya: water, sanitation and hygiene. Synthetic; used for tuning."""
import random

from .engine import Indicator, Layout, Row, count_rows, rate_rows

SLUG = "kenya-wash-q3-2026"
SPLIT = "tuning"
WORKBOOK_TITLE = "Northbridge Relief Kenya: WASH response indicator table, July to September 2026"
LOCATIONS = ["Turkana", "Marsabit", "Garissa"]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("KE-1.1", "People with access to safe water from rehabilitated water points", "People", sex=True),
    Indicator("KE-1.2", "Boreholes rehabilitated", "Boreholes"),
    Indicator("KE-1.3", "Water management committee members trained", "People", sex=True),
    Indicator("KE-1.4", "Water samples passing quality tests", "%", rate=True),
    Indicator("KE-2.1", "Household latrines constructed", "Latrines"),
    Indicator("KE-2.2", "Hygiene kits distributed", "Kits"),
    Indicator("KE-2.3", "People reached through hygiene promotion sessions", "People", sex=True),
    Indicator("KE-3.1", "Schools with functional handwashing stations", "Schools"),
]


def build_rows():
    rng = random.Random(31)
    ind = {i.id: i for i in INDICATORS}
    bh = count_rows(ind["KE-1.2"], PERIODS, {"Turkana": (5, 7), "Marsabit": (4, 4), "Garissa": (5, 5)},
                    rng, ach=(0.75, 1.0))
    water = []
    for r in bh:
        per = rng.randint(1350, 1650)
        tot_t, tot_a = r.target * 1500, r.achieved * per
        fa = round(tot_a * rng.uniform(0.51, 0.54))
        tf = round(tot_t * 0.52)
        water += [Row("KE-1.1", r.period, r.loc, "F", tf, fa), Row("KE-1.1", r.period, r.loc, "M", tot_t - tf, tot_a - fa)]
    wmc = count_rows(ind["KE-1.3"], PERIODS, {"Turkana": (40, 50), "Marsabit": (30, 30), "Garissa": (34, 36)},
                     rng, ach=(0.85, 1.0), female=(0.42, 0.5))
    quality = rate_rows(ind["KE-1.4"], PERIODS, LOCATIONS, 95, rng, ach=(84, 96))
    lat = count_rows(ind["KE-2.1"], PERIODS, {"Turkana": (450, 520), "Marsabit": (300, 360),
                                               "Garissa": (420, 480)}, rng, ach=(0.75, 0.98))
    kits = count_rows(ind["KE-2.2"], PERIODS, {"Turkana": (900, 1000), "Marsabit": (700, 800),
                                                "Garissa": (800, 900)}, rng, ach=(0.84, 0.92))
    hp = count_rows(ind["KE-2.3"], PERIODS, {"Turkana": (3000, 3500), "Marsabit": (2400, 2700),
                                              "Garissa": (2800, 3100)}, rng, ach=(0.86, 1.0), female=(0.53, 0.56))
    schools = count_rows(ind["KE-3.1"], PERIODS, {"Turkana": (4, 6), "Marsabit": (3, 4), "Garissa": (3, 5)},
                         rng, ach=(0.66, 1.0))
    return water + bh + wmc + quality + lat + kits + hp + schools


LAYOUT = Layout()

CLAIMS = {
    # overview
    "bh_total": dict(ind="KE-1.2", fmt="word"),
    "water_total": dict(ind="KE-1.1"),
    "hp_about": dict(ind="KE-2.3", fmt="about"),
    "kits_total": dict(ind="KE-2.2"),
    # water supply
    "bh_total2": dict(ind="KE-1.2"),
    "bh_target": dict(ind="KE-1.2", measure="target"),
    "bh_pct_wrong": dict(ind="KE-1.2", measure="pct_target", fmt="pct",
                         error=dict(type="wrong_target", target_from={"period": "cum"})),
    "bh_turkana": dict(ind="KE-1.2", loc="Turkana", fmt="word"),
    "water_turkana_k": dict(ind="KE-1.1", loc="Turkana", fmt="k1"),
    "water_total2": dict(ind="KE-1.1"),
    "water_f": dict(ind="KE-1.1", sex="F"),
    "water_m": dict(ind="KE-1.1", sex="M"),
    "wmc_total": dict(ind="KE-1.3"),
    "wmc_f": dict(ind="KE-1.3", sex="F"),
    "wmc_m": dict(ind="KE-1.3", sex="M", error=dict(type="split_sum", delta=10)),
    "wq_all": dict(ind="KE-1.4", fmt="pct"),
    "wq_target": dict(ind="KE-1.4", measure="target", fmt="pct"),
    "wq_garissa": dict(ind="KE-1.4", loc="Garissa", fmt="pct%"),
    # sanitation
    "lat_total": dict(ind="KE-2.1"),
    "lat_prev": dict(ind="KE-2.1", period="prev"),
    "lat_pct": dict(ind="KE-2.1", measure="pct_target", fmt="pct"),
    # hygiene
    "hp_total": dict(ind="KE-2.3"),
    "hp_turkana": dict(ind="KE-2.3", loc="Turkana"),
    "hp_marsabit": dict(ind="KE-2.3", loc="Marsabit"),
    "hp_garissa": dict(ind="KE-2.3", loc="Garissa", error=dict(type="transposed")),
    "hp_share_f": dict(ind="KE-2.3", sex="F", measure="share", fmt="pct"),
    "kits_over": dict(ind="KE-2.2", error=dict(type="hedge_overstates")),
    # schools
    "schools_total": dict(ind="KE-3.1", error=dict(type="previous_quarter")),
    "schools_target": dict(ind="KE-3.1", measure="target"),
    # next quarter
    "hp_cum_nearly": dict(ind="KE-2.3", period="cum", fmt="nearly"),
}

BLOCKS = [
    ("title", "Emergency Water, Sanitation and Hygiene Response in Turkana, Marsabit and Garissa"),
    ("meta", "Northbridge Relief, Kenya country office. Quarterly report for the period "
             "[[July to September 2026|period]]. Award number [[NR-KE-2026-031|code]]. Version [[1.2|code]], "
             "[[12 October 2026|date]]."),
    ("h1", "[[1|section]]. Overview"),
    ("p", "The third quarter of [[2026|year]] was the hottest and driest of the year in northern Kenya. "
          "Livestock losses continued and many families moved further from their homes in search of water and "
          "pasture. Against this background, Northbridge Relief restored water supply at {bh_total} boreholes, "
          "which now serve {water_total} people. Hygiene promotion teams reached about {hp_about} people with "
          "household and community sessions, and {kits_total} hygiene kits were distributed to families with "
          "young children."),
    ("p", "The response is designed with the county governments and follows the national guidelines for "
          "emergency water trucking and borehole rehabilitation. Water trucking was phased out in Turkana "
          "during the quarter as rehabilitated boreholes came back into use, which lowered the cost of the "
          "response and gave communities a more reliable supply."),
    ("p", "The project works in arid and semi-arid counties where most households depend on livestock and "
          "where shallow wells dry up quickly in the long dry season. Its approach is to bring broken "
          "boreholes back into use, hand them to trained community committees, build household latrines with "
          "families and run hygiene promotion so that safer water leads to better health. Schools are "
          "included because children spend much of the day there and often have no water on site."),
    ("h1", "[[2|section]]. Progress by result area"),
    ("h2", "[[2.1|section]] Water supply"),
    ("p", "Rehabilitation work was completed at {bh_total2} boreholes this quarter against a target of "
          "{bh_target}, or {bh_pct_wrong} of the target. In Turkana, {bh_turkana} boreholes were "
          "rehabilitated, with new solar pumps fitted at [[three|unverifiable]] sites. In Turkana alone, the "
          "rehabilitated boreholes serve {water_turkana_k} people."),
    ("p", "Across the [[three|unverifiable]] counties, the rehabilitated water points give safe water to {water_total2} "
          "people: {water_f} women and girls and {water_m} men and boys. Waiting times at the water points "
          "fell sharply once the second tap stands were installed, and women's groups in Marsabit reported "
          "less conflict at the water points in the evening."),
    ("p", "Water management committees took over the running of the rehabilitated boreholes. The project "
          "trained {wmc_total} committee members in operation, basic repairs and fee collection, {wmc_f} women "
          "and {wmc_m} men, so that every committee now has at least [[two|unverifiable]] women in leadership "
          "roles."),
    ("p", "Water quality testing found that {wq_all} of samples met the national standard for drinking water, "
          "against a target of {wq_target}. Garissa had the lowest result ({wq_garissa}), because [[two|unverifiable]] "
          "shallow wells near the river were contaminated after the August floods; the team chlorinated them "
          "and will test them again in [[October|date]]."),
    ("h2", "[[2.2|section]] Sanitation"),
    ("p", "Families built {lat_total} household latrines with materials and technical support from the "
          "project, up from {lat_prev} in the previous quarter. This is {lat_pct} of the quarterly target. "
          "Latrine construction was slower in Garissa, where flooding in early [[August|date]] damaged "
          "[[37|unverifiable]] pits that had already been dug. Community-led sanitation sessions were held in "
          "[[48|unverifiable]] villages, and [[nine|unverifiable]] villages were declared open-defecation free."),
    ("h2", "[[2.3|section]] Hygiene promotion"),
    ("p", "Hygiene promoters ran sessions on handwashing, safe water storage and menstrual hygiene in all "
          "[[three|unverifiable]] counties. In total, {hp_total} people took part this quarter: {hp_turkana} in "
          "Turkana, {hp_marsabit} in Marsabit and {hp_garissa} in Garissa. Women and girls made up "
          "{hp_share_f} of participants. Over {kits_over} hygiene kits were handed out at the same sessions, "
          "each containing soap, a [[20|measure]]-litre jerrycan and water treatment tablets."),
    ("p", "Promoters used picture cards and radio spots in Turkana and Somali, and the sessions were timed to "
          "fit around water collection and livestock watering. Mothers' groups asked for more sessions on "
          "safe storage of drinking water, which will be added to the curriculum next quarter."),
    ("h2", "[[2.4|section]] Schools"),
    ("p", "In total, {schools_total} schools now have functional handwashing stations, against a target of "
          "{schools_target}. Head teachers in Marsabit reported that attendance improved once water was "
          "available on site, although the project does not yet measure this."),
    ("h1", "[[3|section]]. Accountability to affected people"),
    ("p", "Community members can raise concerns through the toll-free line [[0800 721 316|phone]], suggestion "
          "boxes at water points, or directly with hygiene promoters. The project logged [[163|unverifiable]] "
          "pieces of feedback this quarter, most of them requests for more water points. Complaints about "
          "water fees at [[two|unverifiable]] boreholes in Marsabit were resolved by renegotiating the fee with "
          "the committees."),
    ("h1", "[[4|section]]. Challenges"),
    ("p", "Insecurity along the Marsabit to Moyale road stopped field visits for [[eleven days|duration]] in "
          "[[September|date]]. Spare parts for solar pumps had to be brought from Nairobi, which delayed work at "
          "[[two|unverifiable]] boreholes until the next quarter. Diesel prices rose sharply, and "
          "generator-powered boreholes that the project did not rehabilitate are now running for fewer hours "
          "each day."),
    ("p", "Staff turnover among hygiene promoters was high in Garissa, where other agencies offered longer "
          "contracts. The team responded by training volunteers from the water management committees as "
          "assistant promoters, which also strengthened the link between the committees and the sessions."),
    ("h1", "[[5|section]]. Gender and inclusion"),
    ("p", "Women and girls carry most of the burden of water collection in all programme areas, so the "
          "location of tap stands and the opening hours of water points were agreed with women's groups before "
          "the work started. Latrine designs include a handrail and a wider door for older people and people "
          "with disabilities, and households with a member who cannot walk to a water point were linked to "
          "neighbours who collect water for them through the committees."),
    ("p", "Menstrual hygiene sessions were run by female promoters for girls and women only, and the kits "
          "include reusable pads chosen after consultation with schoolgirls in Turkana. Boys and men were "
          "reached through separate sessions at markets and livestock watering points, where promoters "
          "discussed the cost of illness in the family and the role of men in keeping water clean at home."),
    ("h1", "[[6|section]]. Monitoring and data quality"),
    ("p", "Field officers record activities on mobile forms that are synchronised whenever a connection is "
          "available. The monitoring officer checks the forms each week against the attendance sheets and "
          "the delivery notes before the figures are added to the indicator table. During the quarter a spot "
          "check in Marsabit found that some sessions had been recorded twice; the duplicates were removed "
          "before this report was written."),
    ("p", "Water quality is tested at the point of collection and in a sample of households, because water "
          "that is safe at the tap can be contaminated during transport and storage. Results are shared with "
          "the county public health officers, who follow up any water point that fails a test."),
    ("h1", "[[7|section]]. Operations and logistics"),
    ("p", "Materials for latrines and borehole repairs were bought through framework agreements with "
          "suppliers in Nairobi and Garissa. Transport costs rose with the price of diesel, and the team "
          "reorganised deliveries so that each truck served several sites on one trip. The Lodwar warehouse "
          "was cleared and restocked in [[August|date]], and a stock count at the end of the quarter matched "
          "the records."),
    ("p", "The project worked with local fundis, who were trained by the county water department on "
          "borehole maintenance. Using local labour shortened the time needed for repairs and left skills in "
          "the communities that will be needed after the project ends."),
    ("h1", "[[8|section]]. Coordination"),
    ("p", "Northbridge Relief attended the county WASH coordination forums in Lodwar, Marsabit town and "
          "Garissa and reported its progress to the national WASH cluster each month (see the "
          "[[4W|code]] matrix, sheet [[3|page]]). Borehole rehabilitation sites were agreed with the county "
          "water departments to avoid duplication with [[two|unverifiable]] other agencies."),
    ("h1", "[[9|section]]. Lessons learned"),
    ("p", "Rehabilitating existing boreholes was faster and cheaper than drilling new ones, but only where "
          "the committees were ready to collect fees for maintenance. Where the committee was new, the team "
          "needed more time for training before handing over the water point. Next year the project will "
          "start committee training before the repair work begins, rather than after it."),
    ("p", "Hygiene promotion had the most effect when it was linked to a visible change, such as a new tap "
          "stand or a handwashing station at the school. Sessions held without such a change drew fewer "
          "people and were less well remembered when the team asked participants about them a month later."),
    ("h1", "[[10|section]]. Next quarter"),
    ("p", "In the last quarter of the year the project will rehabilitate the remaining [[four|unverifiable]] "
          "boreholes and expand hygiene promotion to schools in Garissa. Cumulatively, the project has now "
          "reached nearly {hp_cum_nearly} people with hygiene promotion since [[April|date]]."),
    ("meta", "Report prepared by the Kenya WASH programme team, Lodwar office."),
]

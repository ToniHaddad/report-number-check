"""Lebanon: multipurpose cash assistance. Synthetic; used for tuning."""
import random

from .engine import Indicator, Layout, Row, count_rows, rate_rows

SLUG = "lebanon-cash-q3-2026"
SPLIT = "tuning"
WORKBOOK_TITLE = "Northbridge Relief Lebanon: MPCA indicator tracking table, Q2 and Q3 2026"
LOCATIONS = ["Akkar", "Tripoli", "Bekaa"]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("LB-1.1", "Households receiving multipurpose cash assistance", "Households"),
    Indicator("LB-1.2", "People in households receiving cash assistance", "People", sex=True),
    Indicator("LB-1.3", "Cash transferred to households", "USD"),
    Indicator("LB-2.1", "Post-distribution monitoring surveys completed", "Surveys"),
    Indicator("LB-2.2", "Households reporting they can meet their basic needs", "%", rate=True),
    Indicator("LB-3.1", "Complaints and feedback cases received", "Cases", has_target=False),
    Indicator("LB-3.2", "Complaints and feedback cases closed within 14 days", "Cases", has_target=False),
    Indicator("LB-4.1", "Staff and volunteers trained on safeguarding", "People", sex=True),
]


def build_rows():
    rng = random.Random(14)
    ind = {i.id: i for i in INDICATORS}
    hh = count_rows(ind["LB-1.1"], PERIODS, {"Akkar": (1200, 1400), "Tripoli": (1000, 1100),
                                              "Bekaa": (1100, 1300)}, rng, ach=(0.82, 0.97))
    people, cash = [], []
    for r in hh:
        size = rng.uniform(4.5, 4.9)
        tot_t, tot_a = round(r.target * 4.6), round(r.achieved * size)
        fa = round(tot_a * rng.uniform(0.505, 0.525))
        tf = round(tot_t * 0.51)
        people += [Row("LB-1.2", r.period, r.loc, "F", tf, fa), Row("LB-1.2", r.period, r.loc, "M", tot_t - tf, tot_a - fa)]
        cash.append(Row("LB-1.3", r.period, r.loc, "A", r.target * 435, r.achieved * 435 - 145 * rng.randint(3, 30)))
    surveys = count_rows(ind["LB-2.1"], PERIODS, {"Akkar": (140, 150), "Tripoli": (110, 120),
                                                   "Bekaa": (130, 140)}, rng, ach=(0.9, 1.0))
    basic = rate_rows(ind["LB-2.2"], PERIODS, LOCATIONS, 70, rng, ach=(55, 68))
    received = count_rows(ind["LB-3.1"], PERIODS, {"Akkar": (100, 100), "Tripoli": (100, 100),
                                                    "Bekaa": (100, 100)}, rng, ach=(0.8, 1.6))
    closed = [Row("LB-3.2", r.period, r.loc, "A", None, round(r.achieved * rng.uniform(0.72, 0.9))) for r in received]
    trained = count_rows(ind["LB-4.1"], PERIODS, {"Akkar": (14, 16), "Tripoli": (12, 12),
                                                   "Bekaa": (14, 16)}, rng, ach=(0.85, 1.0), female=(0.5, 0.6))
    return hh + people + cash + surveys + basic + received + closed + trained


LAYOUT = Layout()

CLAIMS = {
    # summary
    "hh_total": dict(ind="LB-1.1"),
    "hh_pct": dict(ind="LB-1.1", measure="pct_target", fmt="pct",
                   error=dict(type="wrong_target", target_from={"period": "prev"})),
    "ppl_nearly": dict(ind="LB-1.2", fmt="nearly"),
    "cash_m": dict(ind="LB-1.3", fmt="m2"),
    "pdm_basic": dict(ind="LB-2.2", fmt="pct"),
    "pdm_basic_target": dict(ind="LB-2.2", measure="target", fmt="pct"),
    # output 1
    "hh_total2": dict(ind="LB-1.1"),
    "hh_target": dict(ind="LB-1.1", measure="target"),
    "hh_akkar": dict(ind="LB-1.1", loc="Akkar"),
    "hh_tripoli": dict(ind="LB-1.1", loc="Tripoli", error=dict(type="transposed")),
    "hh_bekaa": dict(ind="LB-1.1", loc="Bekaa"),
    "hh_prev": dict(ind="LB-1.1", period="prev"),
    "ppl_total": dict(ind="LB-1.2"),
    "ppl_f": dict(ind="LB-1.2", sex="F"),
    "ppl_m": dict(ind="LB-1.2", sex="M", error=dict(type="split_sum", delta=100)),
    "ppl_share_half": dict(ind="LB-1.2", sex="F", measure="share", fmt="frac_over"),
    # output 2
    "pdm_total": dict(ind="LB-2.1"),
    "pdm_target": dict(ind="LB-2.1", measure="target"),
    "pdm_bekaa": dict(ind="LB-2.2", loc="Bekaa", fmt="pct"),
    "pdm_akkar": dict(ind="LB-2.2", loc="Akkar", fmt="pct"),
    # output 3
    "cfm_total": dict(ind="LB-3.1"),
    "cfm_closed": dict(ind="LB-3.2", error=dict(type="previous_quarter")),
    # output 4
    "sg_total": dict(ind="LB-4.1", fmt="word"),
    "sg_f": dict(ind="LB-4.1", sex="F", fmt="word"),
    # plans
    "cash_cum_over": dict(ind="LB-1.3", period="cum", fmt="m1", error=dict(type="hedge_overstates")),
}

BLOCKS = [
    ("title", "Multipurpose Cash Assistance for Vulnerable Households in North Lebanon and the Bekaa"),
    ("meta", "Northbridge Relief, Lebanon country office. Quarterly narrative report for [[Q3 2026|period]], "
             "covering [[1 July|date]] to [[30 September 2026|date]]. Grant reference [[NR-LB-2026-014|code]]. "
             "Submitted on [[15 October 2026|date]]."),
    ("h1", "[[1|section]]. Summary"),
    ("p", "During the third quarter of [[2026|year]], Northbridge Relief delivered multipurpose cash assistance "
          "to {hh_total} households across Akkar, Tripoli and the Bekaa, reaching {hh_pct} of the quarterly "
          "target. The assisted households include nearly {ppl_nearly} people. In total, USD {cash_m} was "
          "transferred to beneficiary e-cards during the quarter, and [[three|unverifiable]] monthly "
          "distribution rounds were completed on schedule."),
    ("p", "Post-distribution monitoring found that {pdm_basic} of surveyed households could meet their basic "
          "needs for at least [[two weeks|duration]] after a transfer, against a target of {pdm_basic_target}. "
          "Prices for food and fuel continued to rise, and the gap between the transfer value and the cost of "
          "the minimum expenditure basket widened again. The programme remains the main regular source of "
          "income for many of the families it supports, and the team has asked the donor to consider a "
          "transfer value review in the next allocation."),
    ("h1", "[[2|section]]. Context"),
    ("p", "Lebanon's economic crisis continued to erode household purchasing power during the quarter. "
          "According to the inter-agency vulnerability assessment published in [[July|date]], "
          "[[44 percent|unverifiable]] of Syrian refugee households in Akkar reduced the number of meals they "
          "ate each day, and the cost of the survival minimum expenditure basket for a family of "
          "[[five|word]] reached USD [[2,950|unverifiable]] in [[August|date]]. Fuel shortages in the North in "
          "late [[August|date]] slowed transport for [[nine days|duration]] and disrupted the work of retailers "
          "that accept the e-card."),
    ("p", "Refugee and Lebanese households in the programme areas rely on informal daily work, which fell during "
          "the summer as construction slowed. Many families moved to cheaper housing or shared accommodation, "
          "and requests for help with rent increased at every help desk. Northbridge Relief continued to target "
          "households using the inter-agency vulnerability model, verified through home visits, and kept the "
          "caseload mixed between Syrian refugee and Lebanese households in line with the agreement reached "
          "with the local authorities in the North and the Bekaa."),
    ("h1", "[[3|section]]. Progress against results"),
    ("h2", "[[3.1|section]] Output [[1|section]]: Cash transfers delivered"),
    ("p", "Northbridge Relief transferred cash to {hh_total2} households this quarter against a target of "
          "{hh_target}. Akkar accounted for {hh_akkar} households, Tripoli for {hh_tripoli} and the Bekaa for "
          "{hh_bekaa}. Compared with the second quarter, when {hh_prev} households were assisted, the caseload "
          "grew because [[412|unverifiable]] families referred by protection partners were enrolled in "
          "[[July|date]]. The transfer value stayed at USD [[145|unverifiable]] per household per month, as set "
          "by the Basic Assistance Working Group."),
    ("p", "Of the {ppl_total} people living in assisted households, {ppl_f} were women and girls and {ppl_m} "
          "were men and boys. Women and girls therefore made up just over {ppl_share_half} of the people "
          "reached, in line with the profile of the caseload. Households headed by women made up "
          "[[31 percent|unverifiable]] of the caseload, and [[18 percent|unverifiable]] of households included "
          "a person with a disability."),
    ("h2", "[[3.2|section]] Output [[2|section]]: Post-distribution monitoring"),
    ("p", "The monitoring team completed {pdm_total} post-distribution monitoring surveys by phone and in "
          "person, against a target of {pdm_target}. In Tripoli, [[twelve|unverifiable]] surveys had to be "
          "rescheduled after road closures in [[September|date]]. In the Bekaa, {pdm_bekaa} of surveyed "
          "households said they could cover their basic needs, the highest share of the "
          "[[three|unverifiable]] areas. In Akkar the figure was {pdm_akkar}."),
    ("p", "Households continue to spend most of each transfer on food, rent and medicine. Spending on education "
          "rose in [[September|date]] as the school year started, and several families told the monitoring "
          "team that they had delayed paying rent to cover school costs. These findings were shared with the "
          "education and protection teams so that referrals can be made where children are at risk of "
          "leaving school."),
    ("h2", "[[3.3|section]] Output [[3|section]]: Accountability to affected people"),
    ("p", "Households can reach Northbridge Relief through the free hotline on [[81 234 567|phone]], by "
          "WhatsApp on [[+961 3 456 789|phone]], or at the help desks present at every distribution. The "
          "hotline and help desks received {cfm_total} complaints and feedback cases this quarter. Of these, "
          "{cfm_closed} were closed within [[14 days|duration]], the standard set in the feedback procedure "
          "(see Annex [[2|page]], page [[14|page]]). Most cases concerned card activation and the timing of "
          "transfers; [[three|unverifiable]] cases concerned staff conduct and were referred to the "
          "safeguarding focal point the same day."),
    ("h2", "[[3.4|section]] Output [[4|section]]: Safeguarding"),
    ("p", "Safeguarding training continued for field teams and community volunteers. This quarter {sg_total} "
          "staff and volunteers were trained on safeguarding and protection from sexual exploitation and "
          "abuse, {sg_f} of them women. All [[three|unverifiable]] area offices now have a trained safeguarding "
          "focal point, and refresher sessions are planned for every new volunteer."),
    ("h1", "[[4|section]]. Market monitoring"),
    ("p", "Every month the team visits [[36|unverifiable]] shops that accept the e-card to record the price of "
          "[[eleven|unverifiable]] staple items. The price of the food basket rose by [[9 percent|unverifiable]] "
          "between [[June|date]] and [[September|date]], driven by vegetable oil, rice and bread. Shops in "
          "Akkar reported shorter stock cycles, and the team added a question on stock levels to the monthly "
          "visit form so that supply problems are seen before they affect households."),
    ("h1", "[[5|section]]. Challenges and how they were addressed"),
    ("p", "Card activation failures affected [[211|unverifiable]] households in the Bekaa in "
          "[[August|date]]; their transfers arrived [[six days|duration]] late after the bank replaced the "
          "cards. The team now checks every new card at enrolment. In Tripoli, tension between host and "
          "refugee communities at one distribution site led the team to split the site into "
          "[[two|unverifiable]] smaller ones with separate queues."),
    ("p", "Rising prices remain the main risk to the outcome of the programme. Post-distribution monitoring "
          "shows that rent and debt repayment absorb a growing share of each transfer, and nearly [[a third|unverifiable]] of "
          "households reported buying food on credit in [[September|date]]. The team will present these "
          "findings to the Basic Assistance Working Group together with other cash actors."),
    ("h1", "[[6|section]]. Coordination"),
    ("p", "Northbridge Relief co-chaired [[four|unverifiable]] meetings of the Basic Assistance Working Group in "
          "the North and shared its post-distribution monitoring results with partners. Transfer values, "
          "targeting criteria and the referral pathway were aligned with the [[two|unverifiable]] other cash "
          "actors working in Akkar, which reduced the risk of the same household being assisted twice."),
    ("h1", "[[7|section]]. Gender, age and disability inclusion"),
    ("p", "The programme collects sex, age and disability data for every member of an enrolled household, "
          "using the Washington Group short set of questions. Women are named as the card holder in most "
          "households where the husband works away from home, and help desk staff explain the card and the "
          "hotline to them directly. Older people and people with disabilities can nominate a trusted person "
          "to collect the transfer, and the team visits them at home if no one is available."),
    ("p", "Female staff carry out the monitoring interviews with women, and questions about tension in the "
          "household are asked only when the respondent is alone. Where a woman reported pressure over how "
          "the money was spent, the team offered a referral to the gender-based violence partner in the area. "
          "These referrals are recorded by the protection team and are not reported here, to protect the "
          "people concerned."),
    ("h1", "[[8|section]]. Monitoring, evaluation and learning"),
    ("p", "Monitoring follows the plan agreed with the donor at the start of the grant. Each distribution round "
          "is followed by a phone survey of a random sample of households, stratified by area and by "
          "nationality. Results are entered into the indicator tracking table by the monitoring officer and "
          "checked by the programme manager before they are used in this report. The same table is shared "
          "with the donor every quarter."),
    ("p", "The team also reviewed the post-distribution monitoring questionnaire this quarter. Questions on "
          "debt and on coping strategies were aligned with the inter-agency tools so that results can be "
          "compared with other cash actors. A short qualitative study on how households decide what to buy "
          "first will be carried out with a university partner, and its findings will feed into the mid-term "
          "review."),
    ("h1", "[[9|section]]. Risk management"),
    ("p", "The main risks this quarter were price increases, fuel shortages, community tension and the "
          "possibility of fraud at shops that accept the e-card. Price and fuel risks were reported to the donor "
          "as they arose. Shops are visited monthly and a mystery shopper exercise was carried out in "
          "Tripoli in [[September|date]]; it found no evidence that shops were charging card holders more than "
          "cash customers. The risk register was updated and shared with the regional office."),
    ("h1", "[[10|section]]. Lessons learned"),
    ("p", "Phone-based monitoring proved cheaper and faster than household visits, but it under-represents "
          "older people and households without a working phone. In the next round the team will combine phone "
          "surveys with visits to a random sample of households without phones. Help desks at distribution "
          "sites received more feedback from women than the hotline did, which suggests that keeping both "
          "channels open matters. Finally, sharing monitoring results with community committees before the "
          "report is finalised helped the team explain changes in the transfer schedule."),
    ("h1", "[[11|section]]. Plans for the next quarter"),
    ("p", "In the fourth quarter Northbridge Relief plans to reach [[3,600|unverifiable]] households per month, "
          "subject to funding, and to start the winter top-up for households living in tents and unfinished "
          "buildings above [[1,000 metres|measure]]. Since [[April|date]], more than USD {cash_cum_over} has "
          "been transferred through the programme, and a mid-term review is scheduled for "
          "[[November 2026|date]]."),
    ("meta", "Prepared by the Lebanon programme team. Questions about this report: [[+961 1 345 678|phone]]."),
]

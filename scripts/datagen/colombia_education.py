"""Colombia: education in emergencies. Synthetic; HELD OUT.

This report was written before the checker was tuned and is not used while
tuning. Its phrasing and its workbook layout differ from the two tuning
reports on purpose. Only scripts/benchmark.py --final runs on it.
"""
import random

from .engine import Indicator, Layout, Row, count_rows, rate_rows

SLUG = "colombia-education-q3-2026"
SPLIT = "heldout"
WORKBOOK_TITLE = "Northbridge Relief Colombia. Education in Emergencies. Monitoring matrix 2026"
LOCATIONS = ["La Guajira", "Arauca", "Norte de Santander"]
PERIODS = ("Q2 2026", "Q3 2026")

INDICATORS = [
    Indicator("CO-1.1", "Out-of-school children enrolled in accelerated learning classes", "Children", sex=True),
    Indicator("CO-1.2", "Learning kits distributed", "Kits"),
    Indicator("CO-1.3", "Enrolled children attending at least 80% of sessions", "%", rate=True),
    Indicator("CO-2.1", "Teachers trained in psychosocial support", "Teachers", sex=True),
    Indicator("CO-2.2", "Temporary learning spaces set up or rehabilitated", "Spaces"),
    Indicator("CO-3.1", "Parents and caregivers attending school committee meetings", "People", sex=True),
    Indicator("CO-3.2", "School meals served", "Meals"),
]


def build_rows():
    rng = random.Random(7)
    ind = {i.id: i for i in INDICATORS}
    enr = count_rows(ind["CO-1.1"], PERIODS, {"La Guajira": (1300, 1600), "Arauca": (1000, 1250),
                                               "Norte de Santander": (1100, 1400)}, rng, ach=(0.8, 0.95),
                     female=(0.5, 0.54))
    kits = [Row("CO-1.2", r.period, r.loc, "A", None, None) for r in enr if r.sex == "F"]
    for k in kits:
        kids = sum(r.achieved for r in enr if r.period == k.period and r.loc == k.loc)
        tgt = sum(r.target for r in enr if r.period == k.period and r.loc == k.loc)
        k.target, k.achieved = tgt, kids - rng.randint(15, 60)
    att = rate_rows(ind["CO-1.3"], PERIODS, LOCATIONS, 75, rng, ach=(61, 72))
    tt = count_rows(ind["CO-2.1"], PERIODS, {"La Guajira": (30, 34), "Arauca": (24, 26),
                                              "Norte de Santander": (26, 30)}, rng, ach=(0.85, 1.0),
                    female=(0.6, 0.72))
    spaces = count_rows(ind["CO-2.2"], PERIODS, {"La Guajira": (6, 8), "Arauca": (4, 5),
                                                  "Norte de Santander": (5, 6)}, rng, ach=(0.7, 1.0))
    parents = count_rows(ind["CO-3.1"], PERIODS, {"La Guajira": (400, 450), "Arauca": (300, 330),
                                                   "Norte de Santander": (320, 360)}, rng, ach=(0.75, 0.95),
                         female=(0.68, 0.78))
    meals = count_rows(ind["CO-3.2"], PERIODS, {"La Guajira": (70000, 85000), "Arauca": (55000, 65000),
                                                 "Norte de Santander": (60000, 75000)}, rng, ach=(0.8, 0.97))
    return enr + kits + att + tt + spaces + parents + meals


LAYOUT = Layout(
    sheet="Matrix",
    headers=("Code", "Indicator description", "Unit of measure", "Reporting period", "Department", "Gender",
             "Planned", "Actual"),
    sex_labels={"F": "F", "M": "M", "A": "Total"},
    all_loc="Total",
    rate_as_fraction=True,
)

CLAIMS = {
    "enr_total": dict(ind="CO-1.1"),
    "enr_pct": dict(ind="CO-1.1", measure="pct_target", fmt="num0",
                    error=dict(type="wrong_target", target_from={"period": "prev"})),
    "enr_girls": dict(ind="CO-1.1", sex="F"),
    "enr_boys": dict(ind="CO-1.1", sex="M", error=dict(type="split_sum", delta=100)),
    "tt_total": dict(ind="CO-2.1", fmt="Word", error=dict(type="previous_quarter")),
    "tt_f": dict(ind="CO-2.1", sex="F", fmt="word"),
    "att_frac": dict(ind="CO-1.3", fmt="frac"),
    "att_target": dict(ind="CO-1.3", measure="target", fmt="num0"),
    "enr_lg": dict(ind="CO-1.1", loc="La Guajira"),
    "enr_ar": dict(ind="CO-1.1", loc="Arauca"),
    "enr_ns": dict(ind="CO-1.1", loc="Norte de Santander"),
    "enr_girls_share": dict(ind="CO-1.1", sex="F", measure="share", fmt="num0"),
    "enr_prev": dict(ind="CO-1.1", period="prev"),
    "att_ar": dict(ind="CO-1.3", loc="Arauca", fmt="num0"),
    "kits_total": dict(ind="CO-1.2", error=dict(type="transposed")),
    "kits_ns": dict(ind="CO-1.2", loc="Norte de Santander"),
    "spaces_total": dict(ind="CO-2.2", fmt="word"),
    "spaces_target": dict(ind="CO-2.2", measure="target", fmt="word"),
    "tt_lg": dict(ind="CO-2.1", loc="La Guajira"),
    "tt_m": dict(ind="CO-2.1", sex="M", fmt="word"),
    "par_over": dict(ind="CO-3.1", error=dict(type="hedge_overstates")),
    "par_f_share": dict(ind="CO-3.1", sex="F", measure="share", fmt="num0"),
    "meals_total": dict(ind="CO-3.2", fmt="k1"),
    "meals_arauca": dict(ind="CO-3.2", loc="Arauca", error=dict(type="wrong_location", loc="La Guajira")),
    "meals_ns": dict(ind="CO-3.2", loc="Norte de Santander"),
    "meals_pct": dict(ind="CO-3.2", measure="pct_target", fmt="num0"),
}

BLOCKS = [
    ("title", "Education in Emergencies for Displaced and Host-Community Children"),
    ("meta", "Northbridge Relief Colombia. Quarterly progress report, [[third quarter 2026|period]] "
             "([[1/7/2026|date]] to [[30/9/2026|date]]). Project code [[NR-CO-2026-007|code]]."),
    ("h1", "[[1|section]]. Executive summary"),
    ("p", "Between July and September the programme enrolled {enr_total} out-of-school children in "
          "accelerated learning classes in La Guajira, Arauca and Norte de Santander ({enr_pct} per cent of "
          "planned enrolment). Of these learners, {enr_girls} were girls and {enr_boys} were boys. "
          "{tt_total} teachers, {tt_f} of them women, completed the psychosocial support course."),
    ("p", "Attendance is the main concern. Roughly {att_frac} of enrolled children attended at least "
          "[[80 per cent|threshold]] of sessions, short of the {att_target} per cent benchmark agreed with the "
          "donor. Seasonal work in the coffee and palm harvests, the cost of transport and the movement of "
          "families across the border all pulled children away from class."),
    ("p", "The programme works with the departmental education secretariats to offer accelerated learning to "
          "children who have missed years of school, either because they were displaced inside Colombia or "
          "because their families arrived from Venezuela. Classes follow the flexible education models "
          "recognised by the Ministry of Education, so that learners can be placed in the right grade of a "
          "public school once they have caught up. Alongside the classes, the programme trains teachers in "
          "psychosocial support, distributes learning materials, provides a hot meal on each school day and "
          "works with parents through school committees."),
    ("h1", "[[2|section]]. Operating environment"),
    ("p", "Arrivals from Venezuela continued through informal crossings near Cúcuta and Paraguachón. Many "
          "families arrive with children who have been out of school for [[two years|duration]] or more, and "
          "a large share settle in informal settlements on the edge of Riohacha, Maicao and Saravena where "
          "public schools are already full. The Ministry of Education's flexible models allow these children "
          "to catch up and then move into the formal system, which is the route the programme follows."),
    ("p", "Armed group activity in rural Arauca restricted movement for staff and families on several "
          "occasions. Classes were moved to safer community spaces when needed, and no learner or staff member "
          "was harmed. Heavy rain in [[September|date]] damaged roads in southern La Guajira and delayed the "
          "delivery of school meals for a week."),
    ("h1", "[[3|section]]. Results"),
    ("h2", "[[3.1|section]] Access to education"),
    ("p", "Enrolment by department was as follows. La Guajira: {enr_lg}; Arauca: {enr_ar}; Norte de "
          "Santander: {enr_ns}. Girls accounted for {enr_girls_share} per cent of all learners. The figure "
          "stood at {enr_prev} at the end of June, so the programme grew by more than [[400|unverifiable]] "
          "children over the quarter, almost all of them in La Guajira."),
    ("p", "Attendance varied widely. In Arauca, where the security situation interrupted classes, only "
          "{att_ar} per cent of enrolled children attended at least [[80 per cent|threshold]] of sessions. In "
          "the settlements around Riohacha, attendance improved after the programme started paying for a "
          "school bus on [[two|unverifiable]] routes."),
    ("p", "A total of {kits_total} learning kits (notebooks, pencils, a backpack and a reading book) were "
          "handed out, {kits_ns} of them in Norte de Santander. The team also set up {spaces_total} temporary "
          "learning spaces against a target of {spaces_target}, using tents and rehabilitated community "
          "halls."),
    ("h2", "[[3.2|section]] Quality of teaching and wellbeing"),
    ("p", "The psychosocial support course has [[five|unverifiable]] modules on stress, grief, classroom "
          "routines, referral and self-care. In La Guajira {tt_lg} teachers finished all the modules; the rest "
          "of the teachers were in Arauca and Norte de Santander. Only {tt_m} men took the course, reflecting "
          "the profile of the teaching workforce in the programme."),
    ("p", "Teachers reported that learners who had been out of school for long periods needed help with "
          "concentration and with managing conflict in class. Each learning space now has a quiet corner and "
          "a referral list for child protection services."),
    ("h2", "[[3.3|section]] Families and school committees"),
    ("p", "Upwards of {par_over} parents and caregivers attended school committee meetings this quarter, "
          "roughly {par_f_share} per cent of them mothers or female caregivers. Committees in Maicao organised "
          "the rota for preparing school meals and helped the team trace children who had stopped attending."),
    ("p", "School meals remain the strongest incentive to attend. {meals_total} hot meals were served "
          "over the quarter, {meals_pct} per cent of the plan. In Arauca, {meals_arauca} meals were served, "
          "and in Norte de Santander the figure was {meals_ns}."),
    ("h1", "[[4|section]]. Accountability and safeguarding"),
    ("p", "Children and parents can give feedback through suggestion boxes, a WhatsApp line "
          "([[+57 300 555 0142|phone]]) and monthly meetings with the school committees. Most feedback asked "
          "for more places and for classes in the afternoon. All staff and teachers signed the code of conduct "
          "and completed the safeguarding induction before working with children (see section "
          "[[5.2|section]] of the annual plan)."),
    ("h1", "[[5|section]]. Inclusion"),
    ("p", "Children with disabilities are identified at enrolment through a short questionnaire completed with "
          "the parents. Teachers adapt activities for them, and the programme pays for transport where a child "
          "cannot walk to class. Indigenous Wayuu children in La Guajira are taught in mixed groups with a "
          "bilingual assistant, so that they can follow lessons in Spanish while keeping their own language."),
    ("p", "Adolescent girls are at higher risk of leaving school because of domestic work and early "
          "pregnancy. Female teachers lead small group sessions for them on life skills, and the school "
          "committees follow up with families when a girl stops attending. Boys in border areas face "
          "recruitment risks, and the referral list in each learning space includes the child protection "
          "services that can respond to this."),
    ("h1", "[[6|section]]. Monitoring and learning"),
    ("p", "Teachers take attendance every day on paper forms, which field coordinators collect and enter into "
          "the monitoring matrix each week. Enrolment is checked against the national student registration "
          "system once a child has an identity document, so that the same child is not counted twice when "
          "families move between departments."),
    ("p", "Learning progress is measured with a short reading and arithmetic test at enrolment and again "
          "after each cycle. The first results will be available at the end of the year, when the first group "
          "of learners completes the cycle. The team is also documenting how teachers adapt the flexible "
          "models to the reality of each settlement, to share with the Ministry of Education and other "
          "partners in the education cluster."),
    ("h1", "[[7|section]]. Coordination"),
    ("p", "The programme takes part in the education in emergencies working groups in Riohacha and Cúcuta and "
          "reports to the national education cluster each month. Locations for learning spaces were agreed "
          "with the departmental education secretariats and with other organisations running flexible models, "
          "so that services are not duplicated. Learners who complete the cycle are referred to public "
          "schools through the secretariats, which keep places for them where they can."),
    ("h1", "[[8|section]]. Challenges and lessons"),
    ("p", "Recruiting teachers for rural Arauca remains difficult because of insecurity and low pay. The "
          "programme now pairs new teachers with experienced ones for their first month. Attendance data are "
          "collected on paper and entered weekly, which delays follow-up with families; a tablet-based "
          "register will be piloted in [[two|unverifiable]] learning spaces next quarter."),
    ("p", "The lesson from this quarter is that enrolment alone is not a good measure of progress. The "
          "programme will report attendance and transition to the formal system alongside enrolment from now "
          "on, and will review the [[80 per cent|threshold]] attendance threshold with the donor."),
    ("p", "Staff turnover was lower than in the first half of the year after the programme aligned teacher "
          "pay with the rates used by the secretariats. Field coordinators now spend one day a week in the "
          "classroom with new teachers, which has helped them manage large mixed-age groups. The programme "
          "also learned that families respond better to a home visit by a teacher they know than to a phone "
          "call from the office, and home visits will become the standard follow-up for absent learners."),
    ("p", "Finally, the programme depends on the goodwill of community leaders who lend halls and land for "
          "learning spaces. Written agreements are now signed with each of them, setting out who maintains "
          "the space and what happens if the community needs it back during an emergency."),
    ("h1", "[[9|section]]. Outlook"),
    ("p", "In the fourth quarter the programme expects to transfer around [[600|unverifiable]] learners to "
          "formal schools at the start of the new school year in [[January 2027|date]], and to open "
          "[[three|unverifiable]] more learning spaces in Maicao."),
    ("meta", "Prepared by the Colombia education team, Riohacha field office."),
]

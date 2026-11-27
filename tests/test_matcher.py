import pytest

from app import matcher as m
from app.matcher import Match, analyze, evidence_line, fit_score, read_job

JOB = """DevOps Engineer Intern

Requirements
- Experience with Python and Bash
- Hands-on with Docker and Kubernetes
- CI/CD using Jenkins
- Terraform is a plus

Preferred Qualifications
- AWS
- Prometheus or Grafana
"""

RESUME = """Alex Rivera
Skills: Python, Docker, GitHub Actions, AWS (EC2, IAM), Linux
- Built CI/CD pipelines in GitHub Actions that run pytest on every merge
- Containerized a Flask app with Docker
"""


def test_reads_required_and_preferred_sections():
    reqs = read_job(JOB)
    assert reqs.required == {"Python", "Bash", "Docker", "Kubernetes", "CI/CD", "Jenkins"}
    assert reqs.preferred == {"Terraform", "AWS", "Prometheus", "Grafana"}


def test_a_skill_required_anywhere_stays_required():
    reqs = read_job("Requirements\n- Python\nNice to have\n- Python and Go, Rust")
    assert "Python" in reqs.required and "Python" not in reqs.preferred
    assert reqs.preferred == {"Go", "Rust"}


def test_with_no_headings_everything_is_required_unless_marked():
    reqs = read_job("We use Java and Spring Boot. Kafka experience is a plus. Familiarity with Docker helps.")
    assert reqs.required == {"Java", "Spring Boot"}
    assert reqs.preferred == {"Docker"}


def test_matches_with_evidence_and_suggests_related_experience():
    a = analyze(JOB, RESUME)
    matched = {m.skill: m for m in a.matched}
    missing = {m.skill: m for m in a.missing}
    assert set(matched) == {"Python", "Docker", "CI/CD", "AWS"}
    assert matched["CI/CD"].evidence == "Built CI/CD pipelines in GitHub Actions that run pytest on every merge"
    assert matched["Python"].evidence == "Skills: Python, Docker, GitHub Actions, AWS (EC2, IAM), Linux"
    assert matched["Docker"].evidence == "Containerized a Flask app with Docker"
    assert missing["Jenkins"].related == ["GitHub Actions"]
    assert missing["Jenkins"].required is True
    assert missing["Kubernetes"].related == []


def test_scores_required_skills_twice_as_much():
    # required: 6 skills, 3 matched (Python, Docker, CI/CD); preferred: 4, 1 matched (AWS)
    assert analyze(JOB, RESUME).score == round(100 * (2 * 3 + 1) / (2 * 6 + 4))
    assert fit_score([Match("A", True)], []) == 100
    assert fit_score([], [Match("A", False)]) == 0


def test_explains_when_nothing_is_recognised():
    a = analyze("We want a rockstar ninja.", RESUME)
    assert a.score is None
    assert "No skills recognised in the job post" in a.notes[0]
    assert "No skills recognised in the resume" in analyze(JOB, "Hello").notes[-1]


def test_evidence_prefers_experience_over_the_skills_list():
    resume = "Skills: Python, Docker, AWS, Linux, Git\n- Containerized a Flask app with Docker"
    assert evidence_line("Docker", resume) == "Containerized a Flask app with Docker"
    assert evidence_line("AWS", resume) == "Skills: Python, Docker, AWS, Linux, Git"


def test_evidence_is_trimmed_and_cleaned():
    long_line = "- " + "Python " * 60
    line = evidence_line("Python", long_line)
    assert line.startswith("Python") and line.endswith("…") and len(line) <= 180
    long_list = "Skills: " + ", ".join(["Python"] + ["Go"] * 60)
    assert evidence_line("Python", long_list).endswith("…")
    assert evidence_line("Rust", RESUME) is None


def test_very_long_input_is_capped():
    a = analyze("Python\n" * 50_000, "Python\n" * 50_000)
    assert [m.skill for m in a.matched] == ["Python"]


# -- years of experience ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("5+ years of Python", 5),
        ("5 years experience", 5),
        ("5 years in a DevOps role", 5),
        ("3-5 years of Docker", 3),
        ("3 to 5 yrs of hands-on testing", 3),
        ("2–4 years with Kubernetes, preferred", 2),
        ("At least three years of experience", 3),
        ("Minimum of two years", 2),
        ("Experience with Python", None),
        ("Founded in 2019", None),
        ("A 10 year warranty", None),
        ("Our 25 years in business", 25),  # context words cannot tell this apart; a known limit
    ],
)
def test_read_years_finds_the_lowest_number_asked_for(sentence, expected):
    assert m.read_years(sentence) == expected


def test_years_are_listed_per_skill_and_kept_out_of_the_score():
    job = "Requirements\n- 5+ years of Python and Docker\n- At least three years leading teams\n"
    analysis = m.analyze(job, "Python and Docker every day.")
    assert [(y.years, y.skill, y.required) for y in analysis.years] == [
        (5, "Docker", True),
        (5, "Python", True),
        (3, None, True),
    ]
    assert analysis.years[0].label() == "5+ years of Docker"
    assert analysis.years[2].label() == "3+ years of experience"
    # Both skills still matched, so the score is full: years are judged by the person.
    assert analysis.score == 100
    assert any("years of experience" in note for note in analysis.notes)


def test_a_years_line_that_says_preferred_is_not_required():
    reqs = m.read_job("Kubernetes is a plus, 2-4 years with it preferred")
    assert [(y.years, y.skill, y.required) for y in reqs.years] == [(2, "Kubernetes", False)]


def test_no_years_in_the_post_means_no_note():
    analysis = m.analyze("We use Python.", "Python every day.")
    assert analysis.years == []
    assert not any("years of experience" in note for note in analysis.notes)


@pytest.mark.parametrize(
    "sentence, kind",
    [
        ("We are unable to sponsor visas for this position.", "Work authorization"),
        ("Must be a US citizen.", "Work authorization"),
        ("US citizens only, no exceptions.", "Work authorization"),
        ("No visa sponsorship is available.", "Work authorization"),
        ("Active TS/SCI clearance required.", "Security clearance"),
        ("You must hold a security clearance.", "Security clearance"),
        ("Bachelor's degree required in Computer Science.", "Degree"),
        ("Required: BS in engineering or equivalent.", "Degree"),
        ("This role is 100% onsite in Austin.", "On site"),
        ("You must be able to work onsite.", "On site"),
        ("4 days per week in the office.", "On site"),
        ("5 days/week in our New York or San Francisco office.", "On site"),
        ("4 days/week in person with 1 day remote.", "On site"),
        ("Able to work full time, in person, in Chicago starting in January 2027.", "On site"),
        ("This role is in office, full-time.", "On site"),
        ("Hybrid: 2 days/week onsite.", "On site"),
        ("This is an on-site role.", "On site"),
        ("A valid driver's license is required.", "Driving"),
    ],
)
def test_hard_requirements_are_recognised(sentence, kind):
    found = m.read_gates(sentence)
    assert [g.kind for g in found] == [kind]
    assert found[0].sentence == sentence
    assert found[0].advice


@pytest.mark.parametrize(
    "sentence",
    [
        "We sponsor visas and relocation.",
        "A degree is nice to have.",
        "This role is fully remote.",
        "Clearance is not needed for this team.",
        "You will drive our testing strategy.",
        # "in person" and a days-per-week count both show up in lines that are not a location rule.
        "Interviews are conducted in person.",
        "We meet in person twice a year for an offsite.",
        "You will present in person to customers occasionally.",
        "Our team is distributed across 5 offices.",
        "5 days of paid volunteering a week.",
    ],
)
def test_ordinary_lines_are_not_hard_requirements(sentence):
    assert m.read_gates(sentence) == []


def test_each_kind_is_reported_once_in_the_order_it_is_defined():
    job = (
        "Must be able to work onsite.\n"
        "Bachelor's degree required.\n"
        "We cannot sponsor visas.\n"
        "No visa sponsorship is available for this role.\n"
    )
    found = m.read_gates(job)
    assert [g.kind for g in found] == ["Work authorization", "Degree", "On site"]
    # The first sentence that said it is the one quoted.
    assert found[0].sentence == "We cannot sponsor visas."


def test_hard_requirements_reach_the_report_without_touching_the_score():
    job = "Requirements\n- Python\n- We cannot sponsor visas for this role.\n"
    analysis = m.analyze(job, "Python every day.")
    assert [g.kind for g in analysis.gates] == ["Work authorization"]
    assert analysis.score == 100
    assert any("no rewording can satisfy" in note for note in analysis.notes)


def test_a_long_sentence_is_shortened_for_the_page():
    job = "We cannot sponsor visas " + "x" * 300 + "."
    assert len(m.read_gates(job)[0].sentence) == 180


def test_a_score_from_one_skill_is_marked_as_a_hint():
    a = m.analyze("Requirements\nExperience with JIRA.", "I used JIRA daily.")
    assert a.score == 100
    assert a.skills_compared == 1
    assert a.thin
    assert any("1 skill in this post was recognised" in n for n in a.notes)
    assert any("hint at best" in n for n in a.notes)


def test_a_score_from_enough_skills_is_not_marked():
    job = "Requirements\nPython, Docker and AWS.\nKubernetes is required."
    a = m.analyze(job, "Python and Docker.")
    assert a.skills_compared >= m.THIN_EVIDENCE
    assert not a.thin
    assert not any("hint at best" in n for n in a.notes)


def test_no_recognised_skills_is_not_called_thin_because_there_is_no_score():
    a = m.analyze("We want a thoughtful person.", "I am thoughtful.")
    assert a.score is None
    assert not a.thin
    assert any("no score" in n for n in a.notes)


def test_the_thin_note_uses_plural_wording_for_two_skills():
    a = m.analyze("Requirements\nPython and Docker.", "Python and Docker.")
    assert a.skills_compared == 2
    assert any("2 skills in this post were recognised" in n for n in a.notes)


def test_a_job_post_past_the_limit_says_what_was_not_read():
    job = "Requirements\nPython, Docker and AWS.\n" + ("filler\n" * 3000) + "Must be a US citizen.\n"
    a = m.analyze(job, "Python")
    assert a.job_unread == len(job) - m.MAX_TEXT
    assert any("characters of the job post were read" in n for n in a.notes)
    # The point of the note: the gate below the cut was never seen.
    assert [g.kind for g in a.gates] == []


def test_a_resume_past_the_limit_says_so_separately():
    a = m.analyze("Requirements\nPython, Docker and AWS.", "Python\n" + "x" * 25_000)
    assert a.resume_unread == len("Python\n") + 25_000 - m.MAX_TEXT
    assert any("characters of your resume were read" in n for n in a.notes)
    assert not any("job post were read" in n for n in a.notes)


def test_ordinary_lengths_say_nothing_about_truncation():
    a = m.analyze("Requirements\nPython, Docker and AWS.", "Python and Docker.")
    assert (a.job_unread, a.resume_unread) == (0, 0)
    assert not any("were read" in n for n in a.notes)


@pytest.mark.parametrize(
    "sentence",
    [
        "0-1 years as a software engineer",
        "0 to 2 years of experience",
        "0+ years of experience required",
    ],
)
def test_a_floor_of_zero_years_is_not_a_requirement(sentence):
    reqs = m.read_job(f"Requirements\n{sentence}")
    assert reqs.years == []


def test_the_same_years_requirement_stated_twice_is_reported_once():
    job = "Requirements\n5+ years of Python experience.\nAbout you\n5+ years of Python experience."
    assert [(y.years, y.skill) for y in m.read_job(job).years] == [(5, "Python")]


def test_required_wins_when_the_same_years_line_appears_both_ways():
    job = "Preferred\n3 years of Docker experience is a plus.\nRequirements\n3 years of Docker experience."
    years = m.read_job(job).years
    assert [(y.years, y.skill, y.required) for y in years] == [(3, "Docker", True)]


def test_different_year_counts_for_one_skill_are_both_kept():
    job = "Requirements\n5 years of Python experience.\n2 years of Python experience in a team."
    assert sorted(y.years for y in m.read_job(job).years) == [2, 5]


def test_an_entry_level_post_gets_no_years_note():
    job = "Requirements\n0-1 years as a software engineer.\nPython, Docker and AWS."
    analysis = m.analyze(job, "Python and Docker.")
    assert analysis.years == []
    assert not any("years of experience" in note for note in analysis.notes)


RESUME_WITH_DATES = """
Senior Engineer      Dec 2024 to Aug 2025
Engineer             Jul 2021 to Nov 2024
Intern               Jun 2020 to Jul 2020
"""


def test_the_resume_dates_are_added_up():
    a = m.analyze("Requirements\nPython, Docker and AWS.", RESUME_WITH_DATES)
    assert a.resume_years == 4.3  # 52 months of calendar, not 2 + 41 + 9
    assert len(a.resume_spans) == 2  # the two senior roles run straight on


def test_a_plain_years_requirement_is_answered():
    a = m.analyze("Requirements\nA minimum of 3 years of experience.", RESUME_WITH_DATES)
    [years] = a.years
    assert years.verdict(a.resume_years) == "Your resume shows 4.3 years, which clears this."


def test_a_years_requirement_the_resume_falls_short_of_says_by_how_much():
    a = m.analyze("Requirements\nA minimum of 6 years of experience.", RESUME_WITH_DATES)
    [years] = a.years
    assert years.verdict(a.resume_years) == "Your resume shows 4.3 years, which is 1.7 short of this."


def test_a_skill_specific_requirement_is_not_answered_by_total_experience():
    a = m.analyze("Requirements\n3+ years of Python experience.", RESUME_WITH_DATES)
    [years] = a.years
    verdict = years.verdict(a.resume_years)
    assert "cannot say how much of that was Python" in verdict
    assert "yours to judge" in verdict


def test_a_resume_with_no_dates_answers_nothing():
    a = m.analyze("Requirements\n5+ years of experience.", "I am good at computers.")
    assert a.resume_years is None
    assert a.resume_spans == ()
    assert a.years[0].verdict(a.resume_years) is None


def test_the_spans_are_reported_so_the_arithmetic_can_be_checked():
    a = m.analyze("Requirements\nPython.", RESUME_WITH_DATES)
    assert "Jun 2020 to Jul 2020" in a.resume_spans
    assert any("Jul 2021 to Nov 2024" in s and "Dec 2024 to Aug 2025" in s for s in a.resume_spans)

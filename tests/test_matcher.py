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

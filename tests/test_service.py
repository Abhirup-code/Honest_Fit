from app.service import AI_ERROR_MESSAGES, run
from tests.fakes import FakeProvider

JOB = """Requirements
- Python and Docker
- Experience with ServiceNow
- Kubernetes
Nice to have
- PagerDuty
"""
RESUME = """Skills: Python, Docker, ServiceNow
- Wrote Python tools that cut ticket backlog by 20%
"""


def test_without_ai_the_keyword_report_still_works():
    report = run(JOB, RESUME, None)
    assert report.analysis.score is not None
    assert not report.ai.available and "turned off" in report.ai.message


def test_when_ollama_is_off_says_so_and_still_reports():
    report = run(JOB, RESUME, FakeProvider(available=False))
    assert {m.skill for m in report.analysis.matched} == {"Python", "Docker", "ServiceNow"}
    assert "not running" in report.ai.message
    assert report.tips == [] and report.extras == []


def test_ai_finds_extra_requirements_but_only_ones_the_post_really_mentions():
    extras = [
        {"skill": "PagerDuty", "required": False},  # real, not in catalogue: kept
        {"skill": "ServiceNow", "required": True},  # already covered by the catalogue: dropped
        {"skill": "Quantum computing", "required": True},  # never mentioned: invented, dropped
        {"skill": "<script>", "required": True},  # odd characters: dropped
    ]
    report = run(JOB, RESUME, FakeProvider(extras=extras))
    assert [(e.skill, e.required, e.found_in_resume) for e in report.extras] == [("PagerDuty", False, False)]


def test_tips_go_through_the_honesty_guard():
    tips = [
        {
            "original": "Wrote Python tools that cut ticket backlog by 20%",
            "suggestion": "Automated ticket triage with Python tools, cutting the backlog by 20%",
            "reason": "Python",
        },
        {
            "original": "Wrote Python tools that cut ticket backlog by 20%",
            "suggestion": "Wrote Python and Kubernetes tools that cut ticket backlog by 50%",
            "reason": "Kubernetes",
        },
    ]
    report = run(JOB, RESUME, FakeProvider(tips=tips))
    assert len(report.tips) == 1
    assert len(report.blocked) == 1 and "Kubernetes" in report.blocked[0].reason


def test_a_failing_model_does_not_break_the_report():
    report = run(JOB, RESUME, FakeProvider(error="unreachable"))
    assert report.ai_error == "Could not reach Ollama. The keyword analysis above is still complete."
    assert report.analysis.matched


def test_errors_only_ever_show_fixed_text():
    for code, message in AI_ERROR_MESSAGES.items():
        assert run(JOB, RESUME, FakeProvider(error=code)).ai_error.startswith(message)
    # An unexpected code still gets fixed text, never the code or any exception message.
    assert run(JOB, RESUME, FakeProvider(error="secret detail")).ai_error.startswith("The local model failed.")

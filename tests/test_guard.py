import pytest

from app.guard import check_tip, screen
from app.llm import Tip

RESUME = """Skills: Python, Docker, GitHub Actions, AWS
- Built CI pipelines in GitHub Actions that run pytest on every merge
- Cut release testing time by 30% with automated regression suites
"""


def tip(original: str, suggestion: str) -> Tip:
    return Tip(original=original, suggestion=suggestion, reason="")


def test_allows_honest_rewording():
    t = tip(
        "Built CI pipelines in GitHub Actions that run pytest on every merge",
        "Automated CI/CD pipelines with GitHub Actions, running pytest on every merge",
    )
    assert check_tip(t, RESUME).ok


def test_allows_skills_the_resume_shows_elsewhere():
    t = tip(
        "Built CI pipelines in GitHub Actions that run pytest on every merge", "Built Docker-based CI in GitHub Actions"
    )
    assert check_tip(t, RESUME).ok


@pytest.mark.parametrize(
    ("original", "suggestion", "reason"),
    [
        ("Led a team of 40 engineers", "Led a large team", "not in your resume"),
        (
            "Built CI pipelines in GitHub Actions that run pytest on every merge",
            "Built CI pipelines in Jenkins and Kubernetes",
            "adds Jenkins, Kubernetes",
        ),
        (
            "Built CI pipelines in GitHub Actions that run pytest on every merge",
            "Built CI pipelines in GitHub Actions, cutting failures by 45%",
            "adds the number 45",
        ),
        (
            "Cut release testing time by 30% with automated regression suites",
            "Cut release testing time by 60% with automated regression suites",
            "adds the number 60",
        ),
        (
            "- Built CI pipelines in GitHub Actions that run pytest on every merge",
            "built CI pipelines in GitHub Actions that run pytest on every merge",
            "does not change anything",
        ),
    ],
)
def test_blocks_dishonest_or_useless_tips(original, suggestion, reason):
    verdict = check_tip(tip(original, suggestion), RESUME)
    assert not verdict.ok
    assert reason in verdict.reason


def test_keeps_numbers_already_in_the_line():
    t = tip(
        "Cut release testing time by 30% with automated regression suites",
        "Reduced release testing time 30% through automated regression testing",
    )
    assert check_tip(t, RESUME).ok


def test_screen_splits_kept_and_blocked():
    kept, blocked = screen(
        [
            tip("Skills: Python, Docker, GitHub Actions, AWS", "Skills: Python, Docker, GitHub Actions (CI/CD), AWS"),
            tip("Skills: Python, Docker, GitHub Actions, AWS", "Skills: Python, Go, Docker, AWS"),
        ],
        RESUME,
    )
    assert len(kept) == 1
    assert len(blocked) == 1 and "adds Go" in blocked[0].reason

import pytest

from app.skills import SKILLS, find_skills, group_of, mentions, related, term_in_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Python, C++, C#, .NET and Node.js", {"Python", "C++", "C#", ".NET", "Node.js"}),
        ("CI/CD in GitHub Actions; k8s; Postgres", {"CI/CD", "GitHub Actions", "Git", "Kubernetes", "PostgreSQL"}),
        ("Languages: Go, Rust, R", {"Go", "Rust", "R"}),
        ("Go (Golang) and R programming", {"Go", "R"}),
        ("Skills: Excel, React, Helm, Spring Boot", {"Excel", "React", "Helm", "Spring Boot"}),
    ],
)
def test_finds_skills_however_they_are_written(text, expected):
    assert find_skills(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "A go-getter who will react quickly, excel at teamwork, and take the helm.",
        # Known limit: a capitalised word at the start of a sentence ("Rust-free hinges.") looks exactly
        # like the skill, so these examples use the words the way they normally appear mid-sentence.
        "Spring 2026 internship. Add 500 ml of water. Our ad team uses rust-free hinges.",
        "Let's go. R&D budget. Kubernetes node pools need a node.",
    ],
)
def test_ignores_ordinary_words_that_look_like_skills(text):
    assert not (
        {"Go", "React", "Excel", "Helm", "Spring Boot", "R", "Rust", "Node.js", "Machine learning"} & find_skills(text)
    )


def test_every_skill_has_a_unique_name_and_a_group():
    names = [s.name for s in SKILLS]
    assert len(names) == len(set(names))
    assert all(s.group for s in SKILLS)
    assert all(find_skills(s.name) >= {s.name} or s.regex for s in SKILLS)


def test_mentions_and_unknown_terms():
    assert mentions("Kubernetes", "We run K8s")
    assert mentions("PagerDuty", "On-call with PagerDuty")  # not catalogued: plain word search
    assert not mentions("PagerDuty", "on-call rotation")
    assert not term_in_text("   ", "anything")
    assert term_in_text("SOX compliance", "Experience with SOX compliance testing")


def test_related_skills_share_a_purpose():
    assert related("Jenkins", {"GitHub Actions", "GitLab CI", "Python"}) == ["GitHub Actions", "GitLab CI"]
    assert related("Jenkins", {"Python"}) == []
    assert related("Not A Skill", {"Python"}) == []
    assert group_of("Not A Skill") is None

import pytest
from fastapi.testclient import TestClient

from app import examples
from app.main import SECURITY_HEADERS, create_app, fit_label
from app.matcher import MAX_TEXT
from tests.fakes import FakeProvider

TIP = {
    "original": "Built CI pipelines in GitHub Actions that run pytest on every merge",
    "suggestion": "Built and maintained CI/CD pipelines in GitHub Actions, running pytest on every merge",
    "reason": "Speaks to: CI/CD with Jenkins or similar",
}
BAD_TIP = {**TIP, "suggestion": "Built CI/CD pipelines in Jenkins and Kubernetes for 50 services"}


@pytest.fixture
def client():
    return TestClient(
        create_app(lambda: FakeProvider(extras=[{"skill": "PagerDuty", "required": False}], tips=[TIP, BAD_TIP]))
    )


def test_home_page_has_the_form_and_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="job"' in r.text and 'name="resume"' in r.text
    for name, value in SECURITY_HEADERS.items():
        assert r.headers[name] == value


def test_example_link_fills_both_boxes(client):
    r = client.get("/?example=true")
    assert "Junior DevOps Engineer" in r.text and "Alex Rivera" in r.text


def test_full_analysis_page(client):
    r = client.post("/analyze", data={"job": examples.JOB, "resume": examples.RESUME})
    assert r.status_code == 200
    html = r.text
    assert "You have (" in html and "Missing (" in html
    assert "Related experience you can mention: GitHub Actions" in html  # for Jenkins
    assert "PagerDuty" in html
    assert "Honest wording tips" in html and TIP["suggestion"] in html
    assert "Blocked by the honesty guard (1)" in html and "adds Jenkins, Kubernetes" in html


def test_pasted_html_is_shown_as_text_not_run(client):
    r = client.post("/analyze", data={"job": "<script>alert(1)</script> Python", "resume": "Python"})
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text


@pytest.mark.parametrize(
    ("job", "resume", "message"),
    [
        ("", "Python", "paste or upload your resume"),
        ("Python", "   ", "paste or upload your resume"),
        ("x" * (MAX_TEXT + 1), "Python", "up to 20,000 characters"),
    ],
)
def test_explains_bad_form_input(client, job, resume, message):
    r = client.post("/analyze", data={"job": job, "resume": resume})
    assert r.status_code == 422
    assert message in r.text


def test_json_api(client):
    r = client.post("/api/analyze", json={"job": examples.JOB, "resume": examples.RESUME})
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100 and body["label"] == fit_label(body["score"])
    jenkins = next(m for m in body["missing"] if m["skill"] == "Jenkins")
    assert jenkins == {"skill": "Jenkins", "required": True, "related": ["GitHub Actions"]}
    assert body["ai"]["extra_requirements"] == [{"skill": "PagerDuty", "required": False, "found_in_resume": False}]
    assert [t["suggestion"] for t in body["ai"]["tips"]] == [TIP["suggestion"]]
    assert body["ai"]["blocked"][0]["reason"].startswith("adds Jenkins, Kubernetes")


def test_json_api_validates_input(client):
    assert client.post("/api/analyze", json={"job": "", "resume": "x"}).status_code == 422
    assert client.post("/api/analyze", json={"job": "x" * (MAX_TEXT + 1), "resume": "x"}).status_code == 422


def test_works_with_ai_turned_off(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    r = TestClient(create_app()).post("/api/analyze", json={"job": examples.JOB, "resume": examples.RESUME})
    assert r.json()["ai"] == {
        "available": False,
        "message": "AI tips are turned off.",
        "error": None,
        "extra_requirements": [],
        "tips": [],
        "blocked": [],
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("score", "label"), [(None, "No score"), (90, "Strong fit"), (60, "Good fit"), (35, "Stretch"), (10, "Long shot")]
)
def test_fit_labels(score, label):
    assert fit_label(score) == label

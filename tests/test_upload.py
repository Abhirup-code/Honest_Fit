from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import examples
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
PDF = (FIXTURES / "resume.pdf").read_bytes()
DOCX = (FIXTURES / "resume.docx").read_bytes()
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def client():
    return TestClient(create_app(lambda: None))


@pytest.mark.parametrize(
    ("name", "data", "kind"), [("resume.pdf", PDF, "application/pdf"), ("resume.docx", DOCX, DOCX_TYPE)]
)
def test_uploading_a_resume_fills_the_box_and_analyzes_it(client, name, data, kind):
    r = client.post("/analyze", data={"job": examples.JOB, "resume": ""}, files={"resume_file": (name, data, kind)})
    assert r.status_code == 200
    assert f"from {name}. Check the text in the resume box." in r.text
    assert "Containerized an internal Flask tool with Docker" in r.text  # now in the resume box
    assert "You have (" in r.text


def test_an_uploaded_file_takes_the_place_of_pasted_text(client):
    files = {"resume_file": ("resume.pdf", PDF, "application/pdf")}
    r = client.post("/analyze", data={"job": examples.JOB, "resume": "Old pasted resume"}, files=files)
    assert "Old pasted resume" not in r.text
    assert "Alex Rivera" in r.text


def test_pasting_still_works_with_no_file(client):
    r = client.post("/analyze", data={"job": examples.JOB, "resume": examples.RESUME})
    assert r.status_code == 200 and "You have (" in r.text and "Check the text in the resume box" not in r.text


def test_a_bad_file_explains_why_and_keeps_what_was_typed(client):
    files = {"resume_file": ("photo.png", b"\x89PNG\r\n\x1a\n\x00binary", "image/png")}
    r = client.post("/analyze", data={"job": "My job post", "resume": ""}, files=files)
    assert r.status_code == 422
    assert "That file type is not supported" in r.text
    assert "My job post" in r.text


def test_file_names_cannot_inject_html_or_paths(client):
    files = {"resume_file": ("../../etc/<script>alert(1)</script>.txt", b"Python resume", "text/plain")}
    r = client.post("/analyze", data={"job": examples.JOB}, files=files)
    assert "<script>alert(1)</script>" not in r.text
    assert "../../etc" not in r.text
    assert "from script&gt;.txt." in r.text  # only the last part of the name, and escaped


def test_resume_text_api(client):
    r = client.post("/api/resume-text", files={"file": ("resume.docx", DOCX, DOCX_TYPE)})
    assert r.status_code == 200
    body = r.json()
    assert body["file"] == "resume.docx"
    assert body["text"].startswith("Alex Rivera")
    assert body["characters"] == len(body["text"])


def test_resume_text_api_errors(client):
    r = client.post(
        "/api/resume-text", files={"file": ("scan.pdf", (FIXTURES / "scanned.pdf").read_bytes(), "application/pdf")}
    )
    assert r.status_code == 422 and "no selectable text" in r.json()["detail"]
    r = client.post("/api/resume-text", files={"file": ("", b"", "text/plain")})
    assert r.status_code == 422
    assert client.post("/api/resume-text").status_code == 422


def test_the_page_offers_an_accessible_upload(client):
    html = client.get("/").text
    assert 'enctype="multipart/form-data"' in html
    assert '<label for="resume_file"' in html and 'id="resume_file"' in html
    assert "never stored" in html

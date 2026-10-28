import io
import secrets
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app import extract
from app.extract import MAX_PDF_PAGES, MAX_UPLOAD_BYTES, ExtractionError, detect, docx_text, extract_resume

FIXTURES = Path(__file__).parent / "fixtures"


def read(data: bytes) -> str:
    """Extract both in this process and in the sandboxed child process, and require the same outcome."""
    outcomes = []
    for isolate in (False, True):
        try:
            outcomes.append(("text", extract_resume(data, isolate=isolate)))
        except ExtractionError as e:
            outcomes.append(("error", str(e)))
    assert outcomes[0] == outcomes[1], outcomes
    kind, value = outcomes[0]
    if kind == "error":
        raise ExtractionError(value)
    return value


def docx(document_xml: bytes, extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml)
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buffer.getvalue()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def pdf(pages: int, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(612, 792)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize("name", ["resume.pdf", "resume.docx"])
def test_reads_real_pdf_and_word_files(name):
    text = read((FIXTURES / name).read_bytes())
    assert text.startswith("Alex Rivera")
    assert "Skills: Python, Bash, Docker, GitHub Actions" in text
    assert "Containerized an internal Flask tool with Docker" in text


def test_reads_plain_text_and_tidies_it():
    assert read(b"Alex\r\n\r\n\r\n\r\nSkills:\t Python  \n") == "Alex\n\nSkills: Python"


def test_detects_type_by_contents_not_name():
    assert detect((FIXTURES / "resume.pdf").read_bytes()) == "pdf"
    assert detect((FIXTURES / "resume.docx").read_bytes()) == "docx"
    assert detect(b"plain text") == "text"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"x" * (MAX_UPLOAD_BYTES + 1), "over 2 MB"),
        (b"\x89PNG\r\n\x1a\n\x00\x00binary", "not supported"),
        (b"text with a \x00 byte", "not supported"),
        (b"   \n\n  ", "No text found"),
    ],
)
def test_refuses_unusable_files_with_a_clear_reason(data, message):
    with pytest.raises(ExtractionError, match=message):
        read(data)


def test_explains_a_scanned_pdf_with_no_text():
    with pytest.raises(ExtractionError, match="no selectable text"):
        read((FIXTURES / "scanned.pdf").read_bytes())


def test_refuses_long_and_password_protected_pdfs():
    with pytest.raises(ExtractionError, match=f"more than {MAX_PDF_PAGES} pages"):
        read(pdf(MAX_PDF_PAGES + 1))
    with pytest.raises(ExtractionError, match="password protected"):
        read(pdf(1, password=secrets.token_urlsafe(8)))  # a throwaway test password


def test_regression_unsupported_pdf_filter_found_by_fuzzing():
    # Atheris found a PDF whose garbled filter name made pypdf raise NotImplementedError.
    data = (FIXTURES / "fuzz-unsupported-pdf-filter.bin").read_bytes()
    with pytest.raises(ExtractionError, match="could not be read"):
        read(data)


def test_refuses_a_broken_pdf():
    with pytest.raises(ExtractionError, match="could not be read"):
        read(b"%PDF-1.7\nthis is not really a pdf")


def test_word_paragraphs_tabs_and_line_breaks():
    xml = (
        f"<w:document {W}><w:body>"
        "<w:p><w:r><w:t>Alex</w:t></w:r><w:r><w:tab/><w:t>Rivera</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Line one</w:t><w:br/><w:t>Line two</w:t></w:r></w:p>"
        "</w:body></w:document>"
    ).encode()
    assert docx_text(docx(xml)) == "Alex\tRivera\nLine one\nLine two"


@pytest.mark.parametrize(
    "xml",
    [
        # "Billion laughs": nested entities that expand to gigabytes.
        b'<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        b"<w:document><w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>",
        # External entity that would read a local file.
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><x>&xxe;</x>',
        # The same attack in UTF-16, which a simple byte search would miss.
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'.encode("utf-16"),
    ],
)
def test_refuses_xml_entity_attacks_in_any_encoding(xml):
    with pytest.raises(ExtractionError, match="not valid"):
        read(docx(xml))


def test_refuses_a_zip_bomb():
    bomb = docx(b"<w:document>" + b" " * (extract.MAX_DOCX_XML_BYTES + 10) + b"</w:document>")
    assert len(bomb) < 100_000  # tiny on disk, huge when unpacked
    with pytest.raises(ExtractionError, match="too large"):
        read(bomb)


def test_refuses_zips_that_are_not_word_files():
    with pytest.raises(ExtractionError, match="not a Word .docx"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("hello.txt", "a zip with no Word document inside")
        read(buffer.getvalue())
    with pytest.raises(ExtractionError, match="could not be opened"):
        read(b"PK\x03\x04" + b"\x00" * 50)
    with pytest.raises(ExtractionError, match="could not be read"):
        read(docx(b"<w:document><unclosed>"))


def test_refuses_zips_with_too_many_entries(monkeypatch):
    monkeypatch.setattr(extract, "MAX_ZIP_ENTRIES", 2)
    with pytest.raises(ExtractionError, match="not valid"):
        docx_text(docx(b"<x/>", {"a": b"1", "b": b"2"}))


def test_parsing_runs_in_a_separate_process_that_is_stopped_if_slow(monkeypatch):
    # With no time allowed, the parent gives up and kills the child instead of waiting.
    monkeypatch.setattr(extract, "PARSE_TIMEOUT_SECONDS", 0)
    with pytest.raises(ExtractionError, match="took too long"):
        extract_resume((FIXTURES / "resume.pdf").read_bytes())


def test_the_isolated_parser_reports_errors_from_the_child():
    with pytest.raises(ExtractionError, match="no selectable text|could not be read"):
        extract_resume((FIXTURES / "scanned.pdf").read_bytes(), isolate=True)
    with pytest.raises(ExtractionError, match="not valid"):
        extract_resume(docx(b'<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>'), isolate=True)


def test_results_match_with_and_without_isolation():
    data = (FIXTURES / "resume.docx").read_bytes()
    assert extract_resume(data, isolate=True) == extract_resume(data, isolate=False)

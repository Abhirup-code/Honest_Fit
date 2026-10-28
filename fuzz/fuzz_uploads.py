"""Coverage-guided fuzz test (Atheris) for uploaded resume files.

Mutates real PDF and Word files, and builds Word files around fuzzed XML, checking that every
input either gives text or a friendly ExtractionError: never a crash, a hang, or other exception.

Run from the repository root: PYTHONPATH=. python fuzz/fuzz_uploads.py fuzz/corpus -max_total_time=60
"""

import io
import sys
import zipfile

import atheris

with atheris.instrument_imports():
    from app.extract import MAX_TEXT, ExtractionError, extract_resume


def as_docx(xml: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buffer.getvalue()


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    mode = fdp.ConsumeIntInRange(0, 2)
    rest = fdp.ConsumeBytes(fdp.remaining_bytes())
    payload = {0: rest, 1: b"%PDF-" + rest, 2: as_docx(rest)}[mode]
    try:
        text = extract_resume(payload, isolate=False)  # in-process, so the fuzzer sees every branch
    except ExtractionError as e:
        assert str(e), "errors must explain themselves"
        return
    assert text and len(text) <= MAX_TEXT


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()

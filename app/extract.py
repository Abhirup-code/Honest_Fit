"""Turn an uploaded resume (PDF, Word .docx, or plain text) into text, safely.

Uploads are untrusted, and document parsers are a classic way in. So:

- The file type is decided by its contents (magic bytes), never by its name.
- Files are limited to 2 MB, PDFs to 10 pages, and the text to what the app accepts anyway.
- A .docx is a zip of XML: the zip is checked for bombs (size and entry limits) and the XML
  is parsed with defusedxml, which refuses DTDs and entity-expansion attacks in any encoding.
- PDF and Word parsing runs in a separate process with a time and memory limit, so a crafted
  file that hangs or eats memory only takes down that child process, never the app.
"""

from __future__ import annotations

import io
import logging
import multiprocessing as mp
import re
import zipfile
from typing import Literal

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as safe_fromstring

from .matcher import MAX_TEXT

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_DOCX_XML_BYTES = 10 * 1024 * 1024  # uncompressed document.xml
MAX_ZIP_ENTRIES = 1_000
PARSE_TIMEOUT_SECONDS = 10
PARSE_MEMORY_BYTES = 512 * 1024 * 1024

Kind = Literal["pdf", "docx", "text"]

# pypdf logs a warning for every oddity in a broken file. Those files are untrusted uploads,
# so keep their contents out of the logs; failures still become a friendly ExtractionError.
logging.getLogger("pypdf").setLevel(logging.ERROR)
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(Exception):
    """A friendly reason the file could not be read. Safe to show: always fixed text."""


def detect(data: bytes) -> Kind:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise ExtractionError("That file type is not supported. Upload a PDF, a Word .docx, or a .txt file.") from None
    if b"\x00" in data:
        raise ExtractionError("That file type is not supported. Upload a PDF, a Word .docx, or a .txt file.")
    return "text"


def _tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n[ ]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_TEXT]


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ExtractionError("That PDF is password protected. Save an unlocked copy and try again.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError(f"That PDF has more than {MAX_PDF_PAGES} pages. Upload just your resume.")
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
            if sum(map(len, parts)) > MAX_TEXT:
                break
    except ExtractionError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError) as e:
        raise ExtractionError("That PDF could not be read. Try exporting it again, or paste the text.") from e
    return _unwrap("\n".join(parts))


# A PDF has no paragraphs, only lines, so a long bullet comes back split over several lines. pypdf
# leaves a space at the end of a line that wrapped, and none where a line really ends.
_WRAPPED = re.compile(r"[ \t]+\n(?=[^\s•▪◦●·*-])")


def _unwrap(text: str) -> str:
    """Rejoin lines that only broke because the page ran out of width, so a bullet stays one line."""
    return _WRAPPED.sub(" ", text)


def docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            entries = zf.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ExtractionError("That Word file is not valid.")
            try:
                info = zf.getinfo("word/document.xml")
            except KeyError:
                raise ExtractionError(
                    "That is a zip file but not a Word .docx. Upload a .docx, PDF, or .txt."
                ) from None
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise ExtractionError("That Word file is too large to read.")
            with zf.open(info) as f:
                xml = f.read(MAX_DOCX_XML_BYTES + 1)  # never trust the size the zip claims
            if len(xml) > MAX_DOCX_XML_BYTES:
                raise ExtractionError("That Word file is too large to read.")
    except ExtractionError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, NotImplementedError, RuntimeError) as e:
        raise ExtractionError("That Word file could not be opened. Try saving it again as .docx.") from e
    try:
        root = safe_fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as e:
        raise ExtractionError("That Word file is not valid.") from e
    except ParseError as e:
        raise ExtractionError("That Word file could not be read. Try saving it again as .docx.") from e
    lines = []
    for paragraph in root.iter(f"{_W}p"):
        pieces = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t" and node.text:
                pieces.append(node.text)
            elif node.tag == f"{_W}tab":
                pieces.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                pieces.append("\n")
        lines.append("".join(pieces))
    return "\n".join(lines)


def _parse(kind: Kind, data: bytes) -> str:
    try:
        return pdf_text(data) if kind == "pdf" else docx_text(data)
    except ExtractionError:
        raise
    except MemoryError:
        raise ExtractionError("That file needs too much memory to read.") from None
    except Exception as e:  # noqa: BLE001 - parsers raise many types (found by fuzzing); all mean "unreadable"
        raise ExtractionError("That file could not be read. Paste the text instead.") from e


def _child(kind: Kind, data: bytes, conn) -> None:  # pragma: no cover - runs in the child process
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (PARSE_MEMORY_BYTES, PARSE_MEMORY_BYTES))
    except ImportError, ValueError, OSError:
        pass  # memory limits are not enforced on every OS; the time limit still applies
    try:
        conn.send(("ok", _parse(kind, data)))
    except ExtractionError as e:
        conn.send(("error", str(e)))
    except MemoryError:
        conn.send(("error", "That file needs too much memory to read."))
    except Exception:  # noqa: BLE001 - any parser failure becomes a fixed message
        conn.send(("error", "That file could not be read. Paste the text instead."))
    finally:
        conn.close()


def _isolated(kind: Kind, data: bytes) -> str:
    """Parse in a child process that is killed if it runs too long."""
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(kind, data, child), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(PARSE_TIMEOUT_SECONDS):
            raise ExtractionError("That file took too long to read. Paste the text instead.")
        status, value = parent.recv()
    except EOFError:
        raise ExtractionError("That file could not be read. Paste the text instead.") from None
    finally:
        process.kill()
        process.join(1)
        parent.close()
    if status == "error":
        raise ExtractionError(value)
    return value


def extract_resume(data: bytes, isolate: bool = True) -> str:
    """Text from an uploaded resume. Raises ExtractionError with a message safe to show."""
    if not data:
        raise ExtractionError("That file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError("That file is over 2 MB. Upload a smaller file or paste the text.")
    kind = detect(data)
    raw = data.decode("utf-8") if kind == "text" else (_isolated if isolate else _parse)(kind, data)
    text = _tidy(raw)
    if not text:
        if kind == "pdf":
            raise ExtractionError("That PDF has no selectable text (it may be a scan). Paste the text instead.")
        raise ExtractionError("No text found in that file.")
    return text

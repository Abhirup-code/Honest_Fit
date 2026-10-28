# Changelog

All notable changes to Honest Fit are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-28

### Added
- Upload a resume as a PDF, Word .docx, or text file (up to 2 MB). The extracted text fills the resume box so
  you can check it before analyzing. `POST /api/resume-text` returns the same text as JSON.
- Upload safety: type detection by contents, size and page limits, zip-bomb and XML-attack protection with
  defusedxml, and parsing in a separate process with time and memory limits.
- A second Atheris fuzz target for the upload readers, and a property test that any bytes give text or a
  friendly error.

### Fixed
- A malformed PDF with an unknown compression filter raised an unhandled error in the in-process reader.
  Found by the new fuzz target within two minutes; any parser failure now becomes a clear message.

### Security
- pypdf raised to 6.21.2 ahead of the two-week cooldown for six denial-of-service advisories.

## [0.1.0] - 2026-10-28

### Added
- Keyword analysis that works with no AI: a catalogue of about 170 skills with their aliases, required versus
  nice-to-have detection, evidence lines from the resume, related experience for missing skills, and a fit score.
- Local AI with Ollama (default model `llama3.2:3b`): extra requirements the catalogue missed, and wording tips.
- The honesty guard, which blocks tips that quote lines not in the resume, add skills, or add numbers.
- Web page and JSON API (`POST /api/analyze`), with strict security headers and no accessibility violations.
- Docker image (non-root, read-only) and a compose file that runs the app with Ollama.
- CI with tests, property-based fuzzing, a 95% coverage gate, and security scanning.

### Security
- certifi raised to 2026.10.19 (PYSEC-2026-4320) and filelock to 4.2.1 or later in CI tools, ahead of the
  two-week dependency cooldown.

[0.2.0]: https://github.com/Abhirup-code/Honest_Fit/releases/tag/v0.2.0
[0.1.0]: https://github.com/Abhirup-code/Honest_Fit/releases/tag/v0.1.0

# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/Abhirup-code/Honest_Fit/security/advisories/new),
not a public issue. I aim to reply within a week.

## Supported versions

Only the latest version on `main` receives fixes.

## How the project handles your data

- **Local by design.** The app and the model both run on your computer. Nothing you paste is sent to any
  outside service, stored on disk, or logged. Pages that contain your resume are sent with `Cache-Control: no-store`.
- **Bound to localhost.** The Docker setup publishes the app on `127.0.0.1` only.
- **Untrusted input.** Job posts and resumes are length-capped, escaped when shown, and fenced as data in prompts.
  The page's Content-Security-Policy allows no inline or third-party scripts.
- **Untrusted uploads.** Resume files are identified by their contents, not their names, and limited to 2 MB
  and 10 PDF pages. Word files are checked for zip bombs and parsed with defusedxml, which refuses DTD and
  entity-expansion attacks in any encoding. PDF and Word parsing runs in a separate process with a 10-second
  time limit and a memory cap, so a hostile file can only take down that child process. Uploads are never stored.
- **Untrusted model output.** Every answer must match a strict JSON schema. Wording tips then pass the honesty guard,
  which rejects any tip that quotes a line not in your resume, adds a skill the resume does not show, or adds a
  number. Extra requirements must actually appear in the job post.

## Supply chain

- Every Python dependency is pinned with SHA-256 hashes and installed with `--require-hashes`.
- Only versions at least two weeks old are locked in, except security fixes, which are documented in
  `requirements.in` (certifi for PYSEC-2026-4320, and pypdf 6.21.2 for six denial-of-service advisories). Dependabot uses the same two-week cooldown.
- Every GitHub Action is pinned to a full commit hash, and workflows default to read-only permissions.
- CI runs ruff (with security rules), bandit, CodeQL, gitleaks over the full history, pip-audit, Trivy on the
  container image, zizmor on the workflows, dependency review on pull requests, OpenSSF Scorecard, and
  Atheris fuzzing of the analysis, the honesty guard, and the upload readers.

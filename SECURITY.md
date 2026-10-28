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
- **Untrusted model output.** Every answer must match a strict JSON schema. Wording tips then pass the honesty guard,
  which rejects any tip that quotes a line not in your resume, adds a skill the resume does not show, or adds a
  number. Extra requirements must actually appear in the job post.

## Supply chain

- Every Python dependency is pinned with SHA-256 hashes and installed with `--require-hashes`.
- Only versions at least two weeks old are locked in, except security fixes, which are documented in
  `requirements.in` (for example certifi for PYSEC-2026-4320). Dependabot uses the same two-week cooldown.
- Every GitHub Action is pinned to a full commit hash, and workflows default to read-only permissions.
- CI runs ruff (with security rules), bandit, CodeQL, gitleaks over the full history, pip-audit, Trivy on the
  container image, zizmor on the workflows, dependency review on pull requests, and OpenSSF Scorecard.

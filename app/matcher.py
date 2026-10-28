"""Compare a job description with a resume, without any AI: the part that always works."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .skills import find_skills, mentions, related

MAX_TEXT = 20_000

_PREFERRED_HEADING = re.compile(
    r"^\s*(?:#+\s*)?(?:preferred|nice[- ]to[- ]have|bonus|desired|good to have|pluses|extra credit)\b", re.I
)
_REQUIRED_HEADING = re.compile(
    r"^\s*(?:#+\s*)?(?:requirements?|required|qualifications|minimum qualifications|basic qualifications|"
    r"must[- ]haves?|what you(?:'|’)ll need|what you bring|you have|who you are|skills|responsibilities|"
    r"what you(?:'|’)ll do)\b",
    re.I,
)
# A requirement line that says it is optional, even inside a "Requirements" list.
_PREFERRED_LINE = re.compile(
    r"\b(?:preferred|a plus|nice to have|bonus|ideally|desired|is helpful|familiarity)\b", re.I
)
_SENTENCE = re.compile(r"(?<=[.;!?])\s+")


@dataclass
class Requirements:
    required: set[str] = field(default_factory=set)
    preferred: set[str] = field(default_factory=set)


def read_job(job: str) -> Requirements:
    """Which catalogued skills a job post asks for, split into required and nice-to-have."""
    reqs = Requirements()
    section = "required"
    for line in job[:MAX_TEXT].splitlines():
        heading_like = len(line.strip()) <= 60
        if heading_like and _PREFERRED_HEADING.match(line):
            section = "preferred"
        elif heading_like and _REQUIRED_HEADING.match(line):
            section = "required"
        # Judge each sentence on its own: "We use Java. Docker is a plus." makes only Docker optional.
        for sentence in _SENTENCE.split(line):
            found = find_skills(sentence)
            if not found:
                continue
            optional = section == "preferred" or _PREFERRED_LINE.search(sentence)
            (reqs.preferred if optional else reqs.required).update(found)
    reqs.preferred -= reqs.required  # asked for anywhere as required wins
    return reqs


@dataclass
class Match:
    skill: str
    required: bool
    evidence: str | None = None  # the resume line that shows it
    related: list[str] = field(default_factory=list)  # for a missing skill: what you have that is similar


@dataclass
class Analysis:
    score: int | None  # 0-100, or None when the job post names no skills we recognise
    matched: list[Match]
    missing: list[Match]
    resume_skills: set[str]
    notes: list[str] = field(default_factory=list)


_SKILLS_LIST = re.compile(r"^(?:technical\s+)?(?:skills|tools|technologies|tech stack|languages)\b", re.I)


def _is_skills_list(line: str) -> bool:
    return bool(_SKILLS_LIST.match(line)) or line.count(",") >= 4


def evidence_line(skill: str, resume: str) -> str | None:
    """The resume line that best shows the skill: an experience bullet before a bare skills list."""
    fallback = None
    for raw in resume.splitlines():
        line = raw.strip(" \t•-*·")
        if not line or not mentions(skill, line):
            continue
        if not _is_skills_list(line):
            return line if len(line) <= 180 else line[:177].rstrip() + "…"
        fallback = fallback or line
    if fallback and len(fallback) > 180:
        return fallback[:177].rstrip() + "…"
    return fallback


def fit_score(matched: list[Match], missing: list[Match]) -> int | None:
    """Required skills count twice as much as nice-to-haves."""
    weight = lambda m: 2 if m.required else 1  # noqa: E731
    total = sum(map(weight, matched + missing))
    if total == 0:
        return None
    return round(100 * sum(map(weight, matched)) / total)


def analyze(job: str, resume: str) -> Analysis:
    job, resume = job[:MAX_TEXT], resume[:MAX_TEXT]
    reqs = read_job(job)
    have = find_skills(resume)
    matched: list[Match] = []
    missing: list[Match] = []
    for required, skills in ((True, reqs.required), (False, reqs.preferred)):
        for skill in sorted(skills, key=str.lower):
            if skill in have:
                matched.append(Match(skill, required, evidence_line(skill, resume)))
            else:
                missing.append(Match(skill, required, related=related(skill, have)))
    notes = []
    if not reqs.required and not reqs.preferred:
        notes.append("No skills recognised in the job post, so there is no score. Paste the full requirements section.")
    if not have:
        notes.append("No skills recognised in the resume. Paste it as plain text, including your skills section.")
    return Analysis(fit_score(matched, missing), matched, missing, have, notes)

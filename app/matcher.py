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
# "5+ years", "3-5 years of experience", "at least two years". Years are the requirement people
# are screened out on most often, and a skill match alone says nothing about them.
_YEARS = re.compile(
    r"(?:(?P<low>\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)\s*(?P<high>\d{1,2})|(?P<one>\d{1,2})\s*\+?)"
    r"\s*(?:\+\s*)?(?:yrs?|years?)\b",
    re.I,
)
_WORD_YEARS = re.compile(
    r"\b(?:at least|minimum(?: of)?|min\.?)\s+(?P<word>one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+(?:yrs?|years?)\b",
    re.I,
)
# What has to follow the number for it to be a requirement. Without this, "a 10 year warranty"
# and "our 25 years in business" would be read as asking for experience.
_YEARS_CONTEXT = re.compile(r"^\W*(?:of|in|with|experience|exp\b|working|hands[- ]on|building|as\b)", re.I)
_WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


# Requirements no rewording of a resume can satisfy. Finding these early saves an application:
# they are the reason a strong match still gets rejected.
GATES: tuple[tuple[str, str, str], ...] = (
    (
        "Work authorization",
        r"\b(?:must be (?:a )?(?:US|U\.S\.) (?:citizen|person)|US citizenship required|"
        r"citizens? only|no (?:visa )?sponsorship|not (?:able|willing) to sponsor|"
        r"(?:do(?:es)? not|cannot|can't|unable to) (?:provide |offer )?sponsor|"
        r"without (?:current or future )?sponsorship|green card holders?)\b",
        "Check this before applying: it rules out some work authorizations.",
    ),
    (
        "Security clearance",
        r"\b(?:security clearance|(?:active|current)\s+(?:TS/SCI|Secret|Top Secret)|"
        r"TS/SCI|public trust clearance|ability to obtain a clearance)\b",
        "A clearance usually needs citizenship and takes months to get.",
    ),
    (
        "Degree",
        r"\b(?:(?:bachelor(?:'s|s)?|master(?:'s|s)?|BS|BA|MS|PhD)\s*(?:degree)?\s*"
        r"(?:is\s+)?required|required[:,]?\s*(?:bachelor|master|BS|BA|MS|PhD)|degree required)\b",
        "Say where your degree is from and when it finishes.",
    ),
    (
        # Posts say this a dozen ways. "5 days/week in our New York office" and "work full time,
        # in person, in Chicago" are both an on-site requirement, and both were missed when this
        # only looked for "N days per week in the office". The days-per-week branch needs an
        # office word later in the same sentence, so "5 days of paid leave a week" stays out, and
        # "in person" needs a working verb or a place beside it, so "interviews are in person" does
        # too.
        "On site",
        r"(?:on-?site only|100%\s*on-?site|fully\s*on-?site|no remote|remote is not|"
        r"must (?:be able to )?(?:work |report )?(?:on-?site|in(?:-| )office)|"
        r"\d\s*days?\s*(?:/|per|a)\s*week\b(?=[^.]*\b(?:office|on-?site|in[- ]person|in[- ]office)\b)|"
        r"\b(?:role|position|job|work)\s+is\s+(?:fully\s+|100%\s+)?(?:in[- ]office|in[- ]person|on-?site)\b|"
        r"\b(?:is|are)\s+(?:an?\s+)?(?:fully\s+)?(?:in[- ]office|on-?site)\s+(?:role|position|job)\b|"
        r"\bwork\b[^.]{0,30}\bin[- ]person\b|"
        r"\bin[- ]person\b[^.]{0,20}\bin\s+[A-Z][a-z]+|"
        r"\b(?:based|located)\s+(?:in[- ]office|on-?site)\b|"
        r"^\s*in[- ]office\b)",
        "Check the commute, or whether you can relocate.",
    ),
    (
        "Driving",
        r"\b(?:valid driver(?:'s|s)? licen[cs]e|must be able to drive|clean driving record)\b",
        "You need a licence valid where the job is.",
    ),
)


@dataclass(frozen=True)
class Gate:
    """A hard requirement found in the post, with the sentence it came from."""

    kind: str
    advice: str
    sentence: str


@dataclass(frozen=True)
class YearsRequirement:
    """A "N years of X" line from the job post, kept with the sentence it came from."""

    years: int
    skill: str | None  # None when the post says "N years of experience" with no skill named
    required: bool
    sentence: str

    def label(self) -> str:
        what = f" of {self.skill}" if self.skill else " of experience"
        return f"{self.years}+ years{what}"


@dataclass
class Requirements:
    required: set[str] = field(default_factory=set)
    preferred: set[str] = field(default_factory=set)
    years: list[YearsRequirement] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)


def read_years(sentence: str) -> int | None:
    """The smallest number of years a sentence asks for, or None. A range takes its low end,
    because "3-5 years" screens on 3."""
    for match in _YEARS.finditer(sentence):
        if _YEARS_CONTEXT.match(sentence[match.end() : match.end() + 30]):
            return int(match.group("low") or match.group("one"))
    worded = _WORD_YEARS.search(sentence)
    return _WORD_NUMBERS[worded.group("word").lower()] if worded else None


_GATES = tuple((kind, re.compile(pattern, re.I), advice) for kind, pattern, advice in GATES)


def read_gates(job: str) -> list[Gate]:
    """Hard requirements in a job post, at most one per kind, with the sentence that said it."""
    found: dict[str, Gate] = {}
    for line in job[:MAX_TEXT].splitlines():
        for sentence in _SENTENCE.split(line):
            text = " ".join(sentence.split()).strip(" \t•-*·")
            for kind, pattern, advice in _GATES:
                if kind not in found and pattern.search(text):
                    found[kind] = Gate(kind, advice, text[:180])
    return [found[kind] for kind, _, _ in _GATES if kind in found]


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
    for line in job[:MAX_TEXT].splitlines():
        for sentence in _SENTENCE.split(line):
            years = read_years(sentence)
            if years is None:
                continue
            skills = sorted(find_skills(sentence), key=str.lower)
            optional = bool(_PREFERRED_LINE.search(sentence))
            text = " ".join(sentence.split()).strip(" \t•-*·")
            for skill in skills or [None]:
                reqs.years.append(YearsRequirement(years, skill, not optional, text[:180]))
    reqs.gates = read_gates(job)
    reqs.preferred -= reqs.required  # asked for anywhere as required wins
    return reqs


@dataclass
class Match:
    skill: str
    required: bool
    evidence: str | None = None  # the resume line that shows it
    related: list[str] = field(default_factory=list)  # for a missing skill: what you have that is similar


# Under this many recognised skills, the percentage says more about the catalogue than about the
# fit: one required skill matched reads as 100%, which is the most flattering number on the page
# and the least earned. A post can be real and still land here, because it describes the work in
# prose instead of listing tools.
THIN_EVIDENCE = 3


@dataclass
class Analysis:
    score: int | None  # 0-100, or None when the job post names no skills we recognise
    matched: list[Match]
    missing: list[Match]
    resume_skills: set[str]
    notes: list[str] = field(default_factory=list)
    years: list[YearsRequirement] = field(default_factory=list)  # "N years" lines, not scored
    gates: list[Gate] = field(default_factory=list)  # hard requirements, not scored

    @property
    def skills_compared(self) -> int:
        """How many of the post's skills the score is actually based on."""
        return len(self.matched) + len(self.missing)

    @property
    def thin(self) -> bool:
        """True when there is a score but too little behind it to read as a measurement."""
        return self.score is not None and self.skills_compared < THIN_EVIDENCE


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
    if reqs.gates:
        notes.append(
            "This post has requirements no rewording can satisfy, listed below. "
            "Read those first: they decide whether applying is worth it."
        )
    if reqs.years:
        notes.append(
            "This post asks for years of experience. Only you can judge those, "
            "so they are listed separately and are not part of the score."
        )
    result = Analysis(fit_score(matched, missing), matched, missing, have, notes, reqs.years, reqs.gates)
    if result.thin:
        count = result.skills_compared
        one = count == 1
        notes.append(
            f"Only {count} skill{'' if one else 's'} in this post {'was' if one else 'were'} recognised, so "
            f"{result.score}% rests on {count} comparison{'' if one else 's'} and is a hint at best. "
            "Paste the full requirements section, or read the lists below instead of the number."
        )
    return result

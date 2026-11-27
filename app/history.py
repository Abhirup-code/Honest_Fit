"""Reads the dates out of a resume, so "5+ years of experience" can be answered rather than listed.

The matcher finds the years a post asks for and hands them back to the reader, because only they
know their own history. Except that the history is usually right there in the resume they pasted,
written as a column of date ranges, and adding it up is arithmetic rather than judgement.

What this does not do is guess. A range it cannot read is not counted, and nothing here infers how
long someone used a particular skill: a date range says when a job ran, not what was in it.
"""

import datetime as dt
import re
from dataclasses import dataclass

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
# Any longer spelling of the same month: "sept", "september", "Jun.", "June,".
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?"
_YEAR = r"(?:19|20)\d{2}"
# "to", an en dash, an em dash or a hyphen. Spaces around it are optional, and a newline is not
# allowed: two dates on separate lines are two jobs, not one range.
_DASH = r"[ \t]*(?:-|–|—|to|through|until)[ \t]*"
_NOW = r"(?:present|current|now|to date|ongoing)"

_RANGE = re.compile(
    rf"(?P<from_month>{_MONTH})[ \t]+(?P<from_year>{_YEAR})"
    rf"{_DASH}"
    rf"(?:(?P<to_month>{_MONTH})[ \t]+(?P<to_year>{_YEAR})|(?P<now>{_NOW}))",
    re.I,
)


@dataclass(frozen=True)
class Span:
    """One stretch of time a resume claims, as months. The day of the month is never written on a
    resume, so a span runs from the first of its start month to the first of the month after it
    ends, which makes "Jun 2020 to Jul 2020" the two months a reader would count."""

    start: dt.date
    end: dt.date
    text: str

    @property
    def months(self) -> int:
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month


def _month(word: str) -> int:
    return MONTHS[word[:3].lower()]


def _next_month(year: int, month: int) -> dt.date:
    return dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)


def read_spans(text: str, today: dt.date | None = None) -> list[Span]:
    """Every date range in the text, oldest first. Ranges that run backwards are left out."""
    now = today or dt.date.today()
    found = []
    for match in _RANGE.finditer(text):
        start = dt.date(int(match["from_year"]), _month(match["from_month"]), 1)
        if match["now"]:
            end = _next_month(now.year, now.month)
        else:
            end = _next_month(int(match["to_year"]), _month(match["to_month"]))
        if end <= start:
            continue  # "Nov 2024 to Jul 2021" is a typo, not a negative job
        found.append(Span(start, end, " ".join(match.group(0).split())))
    return sorted(found, key=lambda s: (s.start, s.end))

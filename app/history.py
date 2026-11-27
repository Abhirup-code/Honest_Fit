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

# "07/2021", "7/2021", "07/15/2021". A day in the middle is ignored: resumes are counted by
# month, and a range is no more precise than the month it starts in.
_SLASHED = r"(?P<{0}_m>0?[1-9]|1[0-2])/(?:\d{{1,2}}/)?(?P<{0}_y>(?:19|20)\d{{2}})"

_SLASHED_RANGE = re.compile(
    rf"(?<![\d/]){_SLASHED.format('from')}{_DASH}(?:{_SLASHED.format('to')}|(?P<now>{_NOW}))(?![\d/])",
    re.I,
)

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
    """Every date range in the text, oldest first.

    Nothing in the future counts as experience. A range starting after this month is dropped
    outright, and one that merely ends later is clipped to this month: a job someone is still
    doing has been done up to now and no further, whatever end date they typed.
    """
    now = today or dt.date.today()
    this_month = _next_month(now.year, now.month)
    found = []
    for match in _RANGE.finditer(text):
        start = dt.date(int(match["from_year"]), _month(match["from_month"]), 1)
        if start >= this_month:
            continue  # work that has not happened yet is not experience
        if match["now"]:
            end = this_month
        else:
            end = min(_next_month(int(match["to_year"]), _month(match["to_month"])), this_month)
        if end <= start:
            continue  # "Nov 2024 to Jul 2021" is a typo, not a negative job
        found.append(Span(start, end, " ".join(match.group(0).split())))

    for match in _SLASHED_RANGE.finditer(text):
        start = dt.date(int(match["from_y"]), int(match["from_m"]), 1)
        if start >= this_month:
            continue
        end = this_month if match["now"] else _next_month(int(match["to_y"]), int(match["to_m"]))
        end = min(end, this_month)
        if end <= start:
            continue
        found.append(Span(start, end, " ".join(match.group(0).split())))

    return sorted(found, key=lambda s: (s.start, s.end))


def merge(spans: list[Span]) -> list[Span]:
    """Overlapping and touching spans combined, so time is counted once.

    Two jobs at once, or a contract that ran alongside a staff role, are two spans covering the
    same months. Adding their lengths would claim more experience than the calendar allows. Spans
    that merely touch are joined too: Jul 2021 to Nov 2024 followed by Dec 2024 is one unbroken
    stretch, and reporting it as two invites an off-by-one at the join.
    """
    merged: list[Span] = []
    for span in sorted(spans, key=lambda s: (s.start, s.end)):
        if merged and span.start <= merged[-1].end:
            last = merged[-1]
            if span.end > last.end:
                merged[-1] = Span(last.start, span.end, f"{last.text}, {span.text}")
        else:
            merged.append(span)
    return merged


def total_months(spans: list[Span]) -> int:
    """Months covered by these spans, counting any month once however many jobs filled it."""
    return sum(span.months for span in merge(spans))


def total_years(spans: list[Span]) -> float:
    """Months as years, to one decimal. 41 months is 3.4 years, not "about three"."""
    return round(total_months(spans) / 12, 1)

"""The honesty guard: AI wording tips may only rephrase what the resume already says."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .llm import Tip
from .skills import find_skills

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_BULLET = re.compile(r"^[\s•\-*·]+")


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", _BULLET.sub("", text)).strip().lower()


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""


def check_tip(tip: Tip, resume: str) -> Verdict:
    original, suggestion = tip.original.strip(), tip.suggestion.strip()
    resume_lines = {_normal(line) for line in resume.splitlines() if line.strip()}
    if _normal(original) not in resume_lines and _normal(original) not in _normal(resume):
        return Verdict(False, "quotes a line that is not in your resume")
    if _normal(suggestion) == _normal(original):
        return Verdict(False, "does not change anything")
    added_skills = sorted(find_skills(suggestion) - find_skills(resume))
    if added_skills:
        return Verdict(False, f"adds {', '.join(added_skills)}, which your resume does not show")
    added_numbers = sorted(set(_NUMBER.findall(suggestion)) - set(_NUMBER.findall(original)))
    if added_numbers:
        return Verdict(False, f"adds the number {', '.join(added_numbers)}, which is not in your original line")
    return Verdict(True)


@dataclass(frozen=True)
class Blocked:
    tip: Tip
    reason: str


def screen(tips: list[Tip], resume: str) -> tuple[list[Tip], list[Blocked]]:
    """Split model suggestions into ones that are safe to show and ones the guard stopped."""
    kept: list[Tip] = []
    blocked: list[Blocked] = []
    for tip in tips:
        verdict = check_tip(tip, resume)
        if verdict.ok:
            kept.append(tip)
        else:
            blocked.append(Blocked(tip, verdict.reason))
    return kept, blocked

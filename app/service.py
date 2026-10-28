"""One analysis: always the keyword match, plus AI extras when a local model is available."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .guard import Blocked, screen
from .llm import AIError, AIProvider, AIStatus, Tip
from .matcher import Analysis, analyze
from .skills import find_skills, term_in_text

# What people see when the model fails. Fixed text only: exception messages are never shown.
AI_ERROR_MESSAGES = {
    "timeout": "The local model took too long to answer.",
    "unreachable": "Could not reach Ollama.",
    "bad_answer": "The model's answer was not in the expected format.",
}
STILL_COMPLETE = "The keyword analysis above is still complete."

_SAFE_TERM = re.compile(r"^[\w .+#/&()'-]{1,60}$")


@dataclass
class ExtraFinding:
    skill: str
    required: bool
    found_in_resume: bool


@dataclass
class Report:
    analysis: Analysis
    ai: AIStatus
    extras: list[ExtraFinding] = field(default_factory=list)
    tips: list[Tip] = field(default_factory=list)
    blocked: list[Blocked] = field(default_factory=list)
    ai_error: str | None = None


def _extras(provider: AIProvider, job: str, resume: str, analysis: Analysis) -> list[ExtraFinding]:
    known = [m.skill for m in analysis.matched + analysis.missing]
    seen = {k.lower() for k in known}
    out: list[ExtraFinding] = []
    for item in provider.extra_requirements(job, known).requirements:
        skill = item.skill.strip()
        # Drop anything odd-looking, anything already covered by the catalogue, and anything
        # the job post never actually mentions (the model must not invent requirements).
        if not _SAFE_TERM.match(skill) or skill.lower() in seen or find_skills(skill):
            continue
        if not term_in_text(skill, job):
            continue
        seen.add(skill.lower())
        out.append(ExtraFinding(skill, item.required, term_in_text(skill, resume)))
    return out


def run(job: str, resume: str, provider: AIProvider | None) -> Report:
    analysis = analyze(job, resume)
    if provider is None:
        return Report(analysis, AIStatus(False, "AI tips are turned off."))
    status = provider.status()
    report = Report(analysis, status)
    if not status.available:
        return report
    try:
        report.extras = _extras(provider, job, resume, analysis)
        matched = [m.skill for m in analysis.matched]
        if matched:
            tips = provider.rewrite_tips(job, resume, matched).tips
            report.tips, report.blocked = screen(tips, resume)
    except AIError as e:
        report.ai_error = f"{AI_ERROR_MESSAGES.get(e.code, 'The local model failed.')} {STILL_COMPLETE}"
    return report

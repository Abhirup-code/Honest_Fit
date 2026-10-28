"""Coverage-guided fuzz test (Atheris) for everything that handles untrusted text.

Job posts, resumes, and model answers are all untrusted. For every generated input this checks:

- analysis never crashes, scores stay 0-100, and no skill is both matched and missing
- the honesty guard never accepts a tip that adds a skill the resume does not show
- the guard never accepts a tip that adds a number the original line did not have
- AI "extra requirements" are only short, safe terms the job post really mentions

Run from the repository root: PYTHONPATH=. python fuzz/fuzz_analysis.py -max_total_time=60
"""

import re
import sys

import atheris

with atheris.instrument_imports():
    from app.guard import check_tip
    from app.llm import ExtraRequirements, Tip, Tips
    from app.matcher import analyze
    from app.service import _SAFE_TERM, run
    from app.skills import SKILLS, find_skills

# Building blocks that steer the fuzzer toward realistic documents quickly.
WORDS = [s.name for s in SKILLS] + [
    "Requirements",
    "Nice to have",
    "Preferred",
    "is a plus",
    "familiarity with",
    "Skills:",
    "- ",
    "\n",
    ", ",
    ". ",
    "40%",
    "3 years",
    "Go-getter",
    "react quickly",
]
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class FuzzProvider:
    """Plays a model that answers with whatever the fuzzer generates."""

    def __init__(self, extras, tips):
        self.extras, self.tips = extras, tips

    def status(self):
        from app.llm import AIStatus

        return AIStatus(True, "fuzz")

    def extra_requirements(self, job, known):
        return ExtraRequirements.model_validate({"requirements": self.extras})

    def rewrite_tips(self, job, resume, matched):
        return Tips.model_validate({"tips": self.tips})


def document(fdp: atheris.FuzzedDataProvider) -> str:
    parts = []
    for _ in range(fdp.ConsumeIntInRange(0, 25)):
        if fdp.ConsumeBool():
            parts.append(WORDS[fdp.ConsumeIntInRange(0, len(WORDS) - 1)])
        else:
            parts.append(fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 40)))
    return " ".join(parts)


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    job, resume = document(fdp), document(fdp)

    # 1. The keyword analysis.
    a = analyze(job, resume)
    assert a.score is None or 0 <= a.score <= 100, a.score
    assert {m.skill for m in a.matched}.isdisjoint({m.skill for m in a.missing})

    # 2. The honesty guard, on a tip built from a real resume line and fuzzed words.
    lines = [line for line in resume.splitlines() if line.strip()] or [resume]
    original = lines[fdp.ConsumeIntInRange(0, len(lines) - 1)].strip()
    suggestion = original + " " + document(fdp)
    if original and suggestion.strip() != original:
        verdict = check_tip(Tip(original=original[:400], suggestion=suggestion[:400], reason=""), resume)
        if verdict.ok:
            assert not (find_skills(suggestion[:400]) - find_skills(resume)), "guard let a new skill through"
            assert set(NUMBER.findall(suggestion[:400])) <= set(NUMBER.findall(original[:400])), "new number"

    # 3. The whole service with a "model" that answers with fuzzed data.
    extras = [
        {"skill": fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 60)) or "x", "required": fdp.ConsumeBool()}
        for _ in range(fdp.ConsumeIntInRange(0, 5))
    ]
    report = run(job, resume, FuzzProvider(extras, []))
    for e in report.extras:
        assert _SAFE_TERM.match(e.skill), e.skill
        assert e.skill.lower() in job.lower(), e.skill


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()

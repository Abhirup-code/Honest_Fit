"""Property-based tests (fuzzing) with Hypothesis: random inputs, rules that must always hold."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.guard import check_tip
from app.llm import Tip
from app.matcher import analyze, read_job
from app.service import run
from app.skills import SKILLS, find_skills
from tests.fakes import FakeProvider

skill_names = st.sampled_from([s.name for s in SKILLS if not s.regex])
words = st.text(alphabet=st.characters(codec="utf-8", exclude_categories=("Cs",)), max_size=200)
lines = st.lists(st.one_of(words, skill_names, st.sampled_from(["Requirements", "Nice to have", "- ", "a plus"])))
documents = lines.map("\n".join)


@settings(max_examples=300, deadline=None)
@given(documents, documents)
def test_analysis_never_crashes_and_scores_stay_in_range(job, resume):
    a = analyze(job, resume)
    assert a.score is None or 0 <= a.score <= 100
    assert {m.skill for m in a.matched}.isdisjoint({m.skill for m in a.missing})
    assert all(m.skill in a.resume_skills for m in a.matched)
    assert all(m.skill not in a.resume_skills for m in a.missing)


@settings(max_examples=300, deadline=None)
@given(documents)
def test_a_skill_is_never_both_required_and_optional(job):
    reqs = read_job(job)
    assert reqs.required.isdisjoint(reqs.preferred)


@settings(max_examples=500, deadline=None)
@given(st.lists(skill_names, min_size=1, max_size=6), st.lists(skill_names, min_size=1, max_size=3), words)
def test_guard_never_lets_a_tip_add_a_skill_the_resume_lacks(resume_skills, added, filler):
    resume = "Skills: " + ", ".join(resume_skills) + "\n- " + filler
    original = resume.splitlines()[0]
    suggestion = original + " and " + ", ".join(added)
    verdict = check_tip(Tip(original=original, suggestion=suggestion, reason=""), resume)
    sneaked_in = find_skills(suggestion) - find_skills(resume)
    if sneaked_in:
        assert not verdict.ok


@settings(max_examples=200, deadline=None)
@given(
    st.lists(
        st.fixed_dictionaries({"skill": st.text(min_size=1, max_size=60), "required": st.booleans()}), max_size=15
    ),
    documents,
    documents,
)
def test_ai_extras_are_only_safe_terms_the_post_mentions(extras, job, resume):
    report = run(job, resume, FakeProvider(extras=extras))
    for e in report.extras:
        assert e.skill.lower() in job.lower()
        assert "<" not in e.skill and ">" not in e.skill


@settings(max_examples=300, deadline=None)
@given(st.binary(max_size=4000), st.sampled_from([b"", b"%PDF-1.7\n", b"PK\x03\x04"]))
def test_any_uploaded_bytes_give_text_or_a_friendly_error(data, prefix):
    from app.extract import ExtractionError, extract_resume

    try:
        text = extract_resume(prefix + data, isolate=False)
    except ExtractionError as e:
        assert str(e)
    else:
        assert text.strip()

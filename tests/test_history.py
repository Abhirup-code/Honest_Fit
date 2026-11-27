import datetime as dt

import pytest

from app.history import Span, merge, read_spans, total_months, total_years

TODAY = dt.date(2026, 11, 26)


def spans(text):
    return read_spans(text, today=TODAY)


def test_a_month_year_range_is_read():
    [span] = spans("Test Project Engineer    Jul 2021 to Nov 2024")
    assert span.start == dt.date(2021, 7, 1)
    assert span.end == dt.date(2024, 12, 1)
    assert span.text == "Jul 2021 to Nov 2024"


def test_a_span_counts_the_month_it_ends_in():
    # "Jun 2020 to Jul 2020" is two months of work to any reader, not one and not zero.
    [span] = spans("Intern   Jun 2020 to Jul 2020")
    assert span.months == 2


@pytest.mark.parametrize(
    "text",
    [
        "June 2020 – August 2020",
        "June 2020 — August 2020",
        "Jun 2020 - Aug 2020",
        "Jun. 2020 to Aug. 2020",
        "jun 2020 through aug 2020",
        "JUNE 2020 TO AUGUST 2020",
    ],
)
def test_the_usual_ways_of_writing_a_range(text):
    [span] = spans(text)
    assert (span.start, span.end) == (dt.date(2020, 6, 1), dt.date(2020, 9, 1))


@pytest.mark.parametrize("word", ["Present", "current", "now", "ongoing", "to date"])
def test_an_open_range_runs_to_this_month(word):
    [span] = spans(f"Engineer   Jan 2026 to {word}")
    assert span.end == dt.date(2026, 12, 1)
    assert span.months == 11


def test_december_rolls_into_the_next_year():
    [span] = spans("Dec 2024 to Dec 2024")
    assert span.end == dt.date(2025, 1, 1)
    assert span.months == 1


def test_spans_come_back_oldest_first():
    text = "Jun 2026 to Aug 2026\nJul 2021 to Nov 2024\nJun 2020 to Jul 2020"
    assert [s.start.year for s in spans(text)] == [2020, 2021, 2026]


def test_a_backwards_range_is_not_a_job():
    assert spans("Nov 2024 to Jul 2021") == []


@pytest.mark.parametrize(
    "text",
    [
        "Expected May 2027",
        "May 2021",
        "Windows 2003/2008/2012 Server",
        "Nov 2024\nJun 2020",  # two lines are two jobs, not one range
        "$50,000 to $70,000",
        "shipped 26 releases to production",
    ],
)
def test_things_that_are_not_date_ranges(text):
    assert spans(text) == []


def test_a_real_resume_gives_one_span_per_job():
    resume = """
    DevSecOps Intern                                      Jun 2026 to Aug 2026
    Senior Test Project Engineer                          Dec 2024 to Aug 2025
    Test Project Engineer                                 Jul 2021 to Nov 2024
    Technology Consulting Virtual Intern                  Jun 2020 to Jul 2020
    """
    found = spans(resume)
    assert len(found) == 4
    assert [s.months for s in found] == [2, 41, 9, 3]


def test_a_span_knows_its_own_length():
    span = Span(dt.date(2021, 1, 1), dt.date(2022, 1, 1), "x")
    assert span.months == 12


def test_two_jobs_at_once_are_counted_once():
    both = spans("Jan 2020 to Dec 2021\nJun 2020 to Dec 2020")
    assert total_months(both) == 24
    assert len(merge(both)) == 1


def test_a_job_inside_another_adds_nothing():
    both = spans("Jan 2020 to Dec 2023\nMar 2021 to Apr 2021")
    assert total_months(both) == 48


def test_back_to_back_jobs_are_one_unbroken_stretch():
    # Nov 2024 ends on the first of December, which is when the next job starts.
    both = spans("Jul 2021 to Nov 2024\nDec 2024 to Aug 2025")
    assert len(merge(both)) == 1
    assert total_months(both) == 50


def test_a_gap_between_jobs_is_not_counted():
    both = spans("Jan 2020 to Dec 2020\nJan 2022 to Dec 2022")
    assert len(merge(both)) == 2
    assert total_months(both) == 24


def test_the_merged_span_keeps_both_descriptions():
    [one] = merge(spans("Jan 2020 to Dec 2021\nJun 2020 to Dec 2022"))
    assert "Jan 2020 to Dec 2021" in one.text and "Jun 2020 to Dec 2022" in one.text


def test_years_are_reported_to_one_decimal():
    assert total_years(spans("Jan 2021 to Dec 2021")) == 1.0
    assert total_years(spans("Jul 2021 to Nov 2024")) == 3.4


def test_nothing_is_no_years():
    assert total_months([]) == 0
    assert total_years([]) == 0.0
    assert merge([]) == []


def test_a_real_resume_adds_up():
    resume = """
    DevSecOps Intern                                      Jun 2026 to Aug 2026
    Senior Test Project Engineer                          Dec 2024 to Aug 2025
    Test Project Engineer                                 Jul 2021 to Nov 2024
    Technology Consulting Virtual Intern                  Jun 2020 to Jul 2020
    """
    found = spans(resume)
    # 2 + 50 (the two Wipro roles run straight on) + 3, not 2 + 41 + 9 + 3 counted blindly.
    assert total_months(found) == 55
    assert total_years(found) == 4.6

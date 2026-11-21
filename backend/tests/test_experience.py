"""Relevant experience (D060): minimum-years parsing, period merging, ISCO grouping."""
from datetime import date

import pytest

from app.matching.experience import (WorkPeriod, isco_group, merged_months, minimum_required_years,
                                     relevant_months)


@pytest.mark.parametrize("text, years", [
    ("- 5+ years of experience as a Machine Learning Engineer", 5),
    ("You have 1-2 years’ experience closing deals", 1),
    ("Minimum of 3 years of industry experience in robotics", 3),
    ("At least 2 years leading teams", 2),
    ("- 7+ years in IT Support, IT Operations or Service Desk", 7),
    ("- Seven to ten years in PR and communications", 7),
    ("Three years of professional experience with Python.", 3),
    ("We need someone with five years experience in sales.", 5),
    ("- +4 years' experience from an institution", 4),
    ("Significant experience (7+ years) in a senior Solutions Engineer role", 7),
    ("Experience: 5 years minimum in embedded hardware design", 5),
    ("with at least 5+ years directly managing partners", 5),
    ("- 4 years + experience in Software Engineering", 4),
    # The first requirement mention wins: later ones are sub-requirements.
    ("Have 4+ years of Product Management experience, including at least 1 year in B2B.", 4),
    ("- 8+ years in design, with 3+ years leading designers", 8),
])
def test_minimum_required_years(text, years):
    assert minimum_required_years(text) == years


@pytest.mark.parametrize("text", [
    "For over 80 years, we have helped mitigate risks.",
    "Lever was founded ten years ago.",
    "We have shaped the internet for the better over the last 25 years.",
    "Your personal data will be retained for up to two years.",
    "Your data is kept for up to 2 years in our candidate pool.",
    "1-month sabbatical after 3 years of service",
    "Most Loved Workplaces (three years running)",
    "Over the next five years, the industry is set to grow 3x.",
    "accounts for 16-17 year olds",
    "After one year on the market, the biggest construction company joined.",
    "From 60M users in 3 years to 100M next.",
    "The contract has a duration of one year.",
    "5+ years of experience is a plus.",  # preference, not a requirement
    "Nice to have: 3 years of experience with Go.",
    "30+ years of experience in the industry",  # above the 25-year bound
    "No years mentioned here.",
    "",
])
def test_non_requirements_are_ignored(text):
    assert minimum_required_years(text) is None


def test_requirement_found_after_a_company_age_sentence():
    text = "For over 30 years we have built tools. Requirements:\n- 3+ years of experience with SQL"
    assert minimum_required_years(text) == 3


def test_periods_merge_overlaps_and_adjacent_months():
    jan20, dec20 = date(2020, 1, 1), date(2020, 12, 1)
    assert merged_months([(jan20, dec20)]) == 12
    assert merged_months([(jan20, dec20), (date(2020, 6, 1), date(2021, 5, 1))]) == 17  # overlap counted once
    assert merged_months([(jan20, dec20), (date(2021, 1, 1), date(2021, 3, 1))]) == 15  # adjacent
    assert merged_months([(jan20, date(2020, 3, 1)), (date(2020, 6, 1), date(2020, 6, 1))]) == 4  # gap
    assert merged_months([(date(2020, 1, 1), date(2022, 1, 1)), (date(2020, 5, 1), date(2020, 7, 1))]) == 25  # nested
    assert merged_months([(dec20, jan20)]) == 0 and merged_months([]) == 0


def test_isco_grouping_uses_three_digits():
    assert isco_group("2512") == "251" and isco_group("2512", 2) == "25" and isco_group("2512", 4) == "2512"
    assert isco_group(None) is None and isco_group("25") is None
    periods = [WorkPeriod(date(2019, 1, 1), date(2020, 12, 1), "2511"),   # systems analyst: same 251 group
               WorkPeriod(date(2020, 7, 1), date(2021, 6, 1), "2512"),    # software developer, overlapping
               WorkPeriod(date(2015, 1, 1), date(2016, 12, 1), "2521"),   # database designer: 252, not related
               WorkPeriod(date(2010, 1, 1), date(2010, 12, 1), None)]     # no occupation chosen
    assert relevant_months(periods, "2512") == 30
    assert relevant_months(periods, "2521") == 24
    assert relevant_months(periods, "2512", digits=2) == 54
    assert relevant_months(periods, None) == 0

"""CV work-entry pre-fill picks the job title, never the company; asks when uncertain (D060)."""
from datetime import date

import pytest

from app.matching.work_history import detect_entries
from app.matching.work_titles import classify, is_company_like

TODAY = date(2026, 11, 21)


def one(text, signal=None):
    entries = detect_entries(text, TODAY, signal)
    assert len(entries) == 1, entries
    return entries[0]


@pytest.mark.parametrize("text", [
    "Data Analyst — Acme GmbH  Jan 2020 – Present",            # Title — Company, dates on the line
    "Data Analyst — Acme GmbH\nJan 2020 - Present",            # Title — Company above the dates
    "Acme Ltd | Data Analyst | 01/2020 - Present",             # Company | Title
    "Acme UAB\nData Analyst\nJan 2020 - Present",              # company above the title
    "Data Analyst\nNordic Bank AS\nJan 2020 - Present",        # title above the company
    "Data Analyst at Example Oy, Jan 2020 - Present",          # one line with both
    "Jan 2020 - Present\nData Analyst\nExample Inc",           # a line with only dates, title below
    "Jan 2020 - Present\nExample LLC\nData Analyst\n• Built dashboards for the sales team.",
])
def test_title_not_company_across_layouts(text):
    entry = one(text)
    assert (entry.title, entry.start_month, entry.end_month) == ("Data Analyst", date(2020, 1, 1), None)
    assert entry.title_choices == ()


def test_only_dates_and_company_offers_no_company_and_guesses_nothing():
    entry = one("Acme GmbH\n2019 - 2021")
    assert entry.title == "" and entry.title_choices == ()


def test_uncertain_lines_are_offered_as_choices_without_companies():
    entry = one("Globex | Contoso Bank\nNorthwind\n03/2019 - 05/2021")
    assert entry.title == "" and entry.title_choices == ("Northwind", "Globex")  # nearest first; bank dropped


def test_two_title_like_parts_ask_the_candidate():
    entry = one("Acme GmbH | Data Analyst | Software Developer | 2019 - 2021")
    assert entry.title == "" and entry.title_choices == ("Data Analyst", "Software Developer")


def test_neighbouring_entries_do_not_leak_into_each_other():
    text = "Data Analyst\nAcme GmbH\n2019 - 2021\n• Reports.\nSoftware Developer\nGlobex SIA\n2016 - 2018"
    assert [e.title for e in detect_entries(text, TODAY)] == ["Data Analyst", "Software Developer"]
    stacked = detect_entries("Data Analyst\n2019 - 2021\nSoftware Developer\n2016 - 2018", TODAY)
    assert stacked[0].title == "" and set(stacked[0].title_choices) == {"Data Analyst", "Software Developer"}
    assert stacked[1].title == "Software Developer"


def test_occupation_signal_marks_titles_without_role_words():
    signal = lambda text: text == "Kita-Erzieherin"
    entry = one("Stadt Musterstadt | Kita-Erzieherin | 2018 - 2020", signal)
    assert entry.title == "Kita-Erzieherin"
    assert one("Stadt Musterstadt | Kita-Erzieherin | 2018 - 2020").title_choices == ("Stadt Musterstadt",
                                                                                      "Kita-Erzieherin")


@pytest.mark.parametrize("text,kind", [
    ("Acme GmbH", "company"), ("Vilnius University", "company"), ("Example S.A.", "company"),
    ("Swedbank AB", "company"), ("Data Analyst", "title"), ("Junior Software Engineer", "title"),
    ("Assistant to the Director", "title"), ("Northwind", "unknown"), ("as needed", "unknown"),
    ("University Lecturer", "title"), ("School Teacher", "title"), ("Group Leader", "title"),
    ("Analyst, Acme GmbH", "company"),  # a legal form always wins
])
def test_classification(text, kind):
    assert classify(text) == kind
    assert is_company_like(text) == (kind == "company")

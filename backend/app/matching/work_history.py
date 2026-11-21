"""Detect dated work entries in CV text, only to pre-fill the candidate's form (D060).

Nothing detected here is stored or used for matching until the candidate
confirms it. Detection looks for a date range on one line ("Jan 2020 -
Present", "03/2018 - 05/2020", "2016 - 2019") in work-experience sections
and takes the rest of that line, or the line above, as a title guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
           "nov": 11, "dec": 12}
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_DATE = (rf"(?:{_MONTH}\.?,?\s+(?:19|20)\d{{2}}|\d{{1,2}}\s*[/.]\s*(?:19|20)\d{{2}}|"
         rf"(?:19|20)\d{{2}}\s*[/.-]\s*\d{{1,2}}(?!\d)|(?:19|20)\d{{2}})")
_OPEN = r"(?:present|current|now|today|ongoing|to date)"
RANGE = re.compile(rf"(?P<start>{_DATE})\s*(?:–|—|-|to|until|till)\s*(?P<end>{_DATE}|{_OPEN})", re.I)
_SPLIT = re.compile(r"\s+(?:at|@)\s+|\s+[|–—-]\s+|,\s+|\t")
WORK_SECTIONS = frozenset({"work_experience", "experience", "full_text"})


@dataclass(frozen=True)
class DetectedEntry:
    title: str
    start_month: date
    end_month: date | None  # None: present
    month_precision: bool  # False when a date had only a year


def parse_month(value: str, is_end: bool, today: date) -> tuple[date | None, bool]:
    """(first day of the month, month known); (None, True) for an open end."""
    value = value.strip().lower()
    if re.fullmatch(_OPEN, value):
        return None, True
    m = re.match(rf"({_MONTH})\.?,?\s+((?:19|20)\d{{2}})", value)
    if m:
        return date(int(m[2]), _MONTHS[m[1][:3]], 1), True
    m = re.match(r"(\d{1,2})\s*[/.]\s*((?:19|20)\d{2})", value)
    if m and 1 <= int(m[1]) <= 12:
        return date(int(m[2]), int(m[1]), 1), True
    m = re.match(r"((?:19|20)\d{2})\s*[/.-]\s*(\d{1,2})$", value)
    if m and 1 <= int(m[2]) <= 12:
        return date(int(m[1]), int(m[2]), 1), True
    m = re.fullmatch(r"(?:19|20)\d{2}", value)
    if m:
        year = int(value)
        month = 12 if is_end else 1
        if is_end and year == today.year:
            month = today.month
        return date(year, month, 1), False
    return None, False


def _title_guess(line: str, match: re.Match, previous: str) -> str:
    rest = (line[:match.start()] + " " + line[match.end():]).strip(" ,|–—-:()\t")
    candidate = rest if len(re.sub(r"[^A-Za-z]", "", rest)) >= 3 else previous
    return _SPLIT.split(candidate.strip())[0].strip(" ,|–—-:()")[:255] if candidate else ""


def detect_entries(text: str, today: date) -> list[DetectedEntry]:
    entries: list[DetectedEntry] = []
    previous = ""
    current_month = date(today.year, today.month, 1)
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        for match in RANGE.finditer(line):
            start, start_known = parse_month(match["start"], False, today)
            end, end_known = parse_month(match["end"], True, today)
            if start is None or start > current_month or (end is not None and (end < start or end > current_month)):
                continue
            if match["end"] and not re.fullmatch(_OPEN, match["end"].strip(), re.I) and end is None:
                continue
            entries.append(DetectedEntry(_title_guess(line, match, previous), start, end, start_known and end_known))
        previous = line
    return entries

"""Detect dated work entries in CV text, only to pre-fill the candidate's form (D060).

Nothing detected here is stored or used for matching until the candidate
confirms it. Detection looks for a date range on one line ("Jan 2020 -
Present", "03/2018 - 05/2020", "2016 - 2019") in work-experience sections.
The job title is chosen from the parts next to it by signal, never a
company-like part; when uncertain the candidate is asked to choose
(`app/matching/work_titles.py`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from app.matching.work_titles import choose_title, parts, short_line

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
           "nov": 11, "dec": 12}
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_DATE = (rf"(?:{_MONTH}\.?,?\s+(?:19|20)\d{{2}}|\d{{1,2}}\s*[/.]\s*(?:19|20)\d{{2}}|"
         rf"(?:19|20)\d{{2}}\s*[/.-]\s*\d{{1,2}}(?!\d)|(?:19|20)\d{{2}})")
_OPEN = r"(?:present|current|now|today|ongoing|to date)"
RANGE = re.compile(rf"(?P<start>{_DATE})\s*(?:–|—|-|to|until|till)\s*(?P<end>{_DATE}|{_OPEN})", re.I)
WORK_SECTIONS = frozenset({"work_experience", "experience", "full_text"})


@dataclass(frozen=True)
class DetectedEntry:
    title: str  # "" when uncertain: the candidate chooses from `title_choices` or types it
    start_month: date
    end_month: date | None  # None: present
    month_precision: bool  # False when a date had only a year
    title_choices: tuple[str, ...] = field(default=())


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


def _adjacent_parts(lines: list[str], index: int, reach: int = 2) -> list[str]:
    """Parts of up to `reach` lines above and below, nearest first; a direction stops at another
    date range, a bullet or a sentence."""
    by_distance: list[list[str]] = [[] for _ in range(reach)]
    for step in (-1, 1):
        for distance in range(1, reach + 1):
            j = index + step * distance
            if not 0 <= j < len(lines) or RANGE.search(lines[j]) or not short_line(lines[j]):
                break
            by_distance[distance - 1].extend(parts(lines[j]))
    return [part for row in by_distance for part in row]


def detect_entries(text: str, today: date, occupation_signal: Callable[[str], bool] | None = None
                   ) -> list[DetectedEntry]:
    entries: list[DetectedEntry] = []
    current_month = date(today.year, today.month, 1)
    lines = [raw.strip() for raw in (text or "").splitlines() if raw.strip()]
    for index, line in enumerate(lines):
        for match in RANGE.finditer(line):
            start, start_known = parse_month(match["start"], False, today)
            end, end_known = parse_month(match["end"], True, today)
            if start is None or start > current_month or (end is not None and (end < start or end > current_month)):
                continue
            if match["end"] and not re.fullmatch(_OPEN, match["end"].strip(), re.I) and end is None:
                continue
            same_line = parts(line[:match.start()] + " | " + line[match.end():])
            choice = choose_title(same_line, _adjacent_parts(lines, index), occupation_signal)
            entries.append(DetectedEntry(choice.title, start, end, start_known and end_known, tuple(choice.choices)))
    return entries

"""Choose the job title for a CV-detected work entry (D060); never the company.

Candidates are the text parts next to a date range: the other parts of the date
line (split at " | ", " - ", " at ", "@", ", ", tabs), then up to two lines
above and below. Scanning a direction stops at another date range, a bullet or
a sentence (the neighbouring entry). Each part is classified:

- company-like: a legal form or organisation word (GmbH, Ltd, Inc, LLC, UAB,
  AB, AS, Oy, SIA, S.A., University, Bank, ...). Never offered as a title.
- title-like: a role word (engineer, analyst, developer, manager, intern, ...)
  or an occupation signal from the caller (strong string match to an ESCO
  occupation, or similar meaning above a threshold).
- unknown: neither.

A title is chosen only when it is the single title-like part on the date line,
or, with none there, the single title-like part on the adjacent lines. Two or
more title-like parts: those are offered as choices ("Which of these is your
job title?"). None: up to four non-company parts are offered, nearest first.
Nothing is guessed when uncertain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

_ROLE = re.compile(
    r"\b(?:engineer|developer|programmer|analyst|scientist|architect|designer|manager|director|head of|lead|"
    r"intern|internship|trainee|apprentice|assistant|associate|specialist|consultant|advisor|adviser|officer|"
    r"administrator|coordinator|technician|researcher|research fellow|lecturer|professor|teacher|tutor|"
    r"instructor|nurse|accountant|auditor|controller|tester|recruiter|representative|executive|editor|writer|"
    r"translator|cashier|barista|waiter|waitress|driver|operator|mechanic|electrician|clerk|secretary|"
    r"receptionist|agent|owner|founder|co-founder|ceo|cto|cfo|coo|vp|vice president|freelancer|"
    r"working student|werkstudent|praktikant|volunteer|supervisor|leader|teller|product owner|scrum master)\b",
    re.I)
# Legal forms always mark a company; organisation words only when the part has no role signal
# ("Vilnius University" is a company, "University Lecturer" a title).
_LEGAL_FORMS = re.compile(
    r"(?:^|(?<=\s))(?:co|s\.a|s\.r\.l|b\.v|n\.v)\.(?=\s|,|$)|"  # dotted forms
    r"\b(?:gmbh|ag|kg|ltd|limited|inc|llc|plc|corp|corporation)\b|&\s*co\b", re.I)
_LEGAL_CASED = re.compile(r"\b(?:UAB|AB|AS|ASA|Oy|Oyj|SIA|SA|SE|BV|NV|OÜ)\b")  # case-sensitive
_ORG_WORDS = re.compile(
    r"\b(?:company|university|universit[äa]t|universidad|college|school|academy|institute|bank|group|holding|"
    r"foundation|hospital|clinic|agency|ministry|municipality|council|association|gymnasium)\b", re.I)
_SPLIT = re.compile(r"\s+(?:at|@)\s+|@|\s+[|–—-]\s+|\s*\|\s*|,\s+|\t+")
_BULLET = re.compile(r"^[\-–—*•·>▪●○◦]\s*")
MAX_WORDS = 8


def is_company_like(text: str, occupation_signal: Callable[[str], bool] | None = None) -> bool:
    if _LEGAL_FORMS.search(text) or _LEGAL_CASED.search(text):
        return True
    return bool(_ORG_WORDS.search(text)) and not _title_signal(text, occupation_signal)


def _title_signal(text: str, occupation_signal: Callable[[str], bool] | None) -> bool:
    return has_role_word(text) or (occupation_signal is not None and occupation_signal(text))


def has_role_word(text: str) -> bool:
    return bool(_ROLE.search(text))


def _clean(part: str) -> str:
    return part.strip(" ,|–—-:()[]\t*•·").strip()


def parts(text: str) -> list[str]:
    return [p for p in (_clean(x) for x in _SPLIT.split(text or "")) if len(re.sub(r"[^\w]", "", p)) >= 2
            and re.search(r"[^\W\d_]{2}", p)]


def short_line(line: str) -> bool:
    """A line that can hold a title or company: not a bullet, not a sentence, not long."""
    stripped = line.strip()
    return bool(stripped) and not _BULLET.match(stripped) and len(stripped.split()) <= MAX_WORDS \
        and not stripped.endswith(".") and len(stripped) <= 120


@dataclass
class TitleChoice:
    title: str  # "" when uncertain
    choices: list[str] = field(default_factory=list)  # offered when uncertain; never company-like
    title_like: int = 0
    company_like: int = 0


def classify(text: str, occupation_signal: Callable[[str], bool] | None = None) -> str:
    if is_company_like(text, occupation_signal):
        return "company"
    return "title" if _title_signal(text, occupation_signal) else "unknown"


MAX_CHOICES = 4


def choose_title(same_line: list[str], adjacent: list[str],
                 occupation_signal: Callable[[str], bool] | None = None) -> TitleChoice:
    """`same_line`: parts of the date line; `adjacent`: parts of nearby lines, nearest first."""
    seen: set[str] = set()

    def label(items: list[str]) -> list[tuple[str, str]]:
        out = []
        for part in items:
            if part.casefold() not in seen:
                seen.add(part.casefold())
                out.append((part[:255], classify(part, occupation_signal)))
        return out

    near, around = label(same_line), label(adjacent)
    every = near + around
    result = TitleChoice("", [], sum(1 for _, k in every if k == "title"), sum(1 for _, k in every if k == "company"))
    for group in (near, around):
        titles = [part for part, kind in group if kind == "title"]
        if len(titles) == 1:
            result.title = titles[0]
            return result
        if len(titles) > 1:
            result.choices = titles[:MAX_CHOICES]
            return result
    result.choices = [part for part, kind in every if kind == "unknown"][:MAX_CHOICES]
    return result

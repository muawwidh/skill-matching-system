"""Relevant experience (DECISIONS.md D060): minimum required years, period merging, ISCO grouping.

Pure functions, no database access. Computed on read; nothing about a job is stored.

Minimum required years (`minimum_required_years`), the rule:

1. A mention is a number (digits 1-25, or a number word one..twenty), optionally
   with "+" or a range ("3-5", "seven to ten"; the lower bound counts), followed
   by "year(s)"/"yr(s)".
2. It is a requirement when either
   a. the next words (at most four, same clause) lead to "experience",
      "expertise" or "track record" ("5+ years of hands-on experience",
      "4 years' experience"), or
   b. it has the shape of a requirement - a "+" sign, a range, a requirement
      cue right before it ("at least", "minimum (of)", "min.", "you have",
      "have", "with", "bring", "requires", "Experience:"), or it starts a
      line or bullet - and is followed (after an optional ")") by
      "of/in/as/within/across/on/at", "minimum", "or more", "professional",
      "relevant", "hands-on", "practical", "industry", "work", or a verb in
      -ing, optionally after an adverb ("5+ years in IT support", "at least 2
      years leading teams", "5+ years directly managing").
3. A mention is dropped when its clause contains a company-age, retention or
   benefit cue: history, founded, established, anniversary, "for over",
   "over the last/past", "next N years", "years running", "of service",
   sabbatical, retain(ed), "kept for", stored, warranty, "years old",
   "year olds", ago, "in business", "on the market", "has/have helped",
   "has/have empowered", "we have been".
4. A mention inside a preference clause ("preferred", "nice to have",
   "ideally", "a plus", "bonus", "advantage") is skipped.
5. The first remaining mention in the posting is the minimum: postings state
   the headline requirement first and sub-requirements later ("4+ years of
   product management experience, including at least 1 year ...").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
                "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
MAX_YEARS = 25
_NUMBER = r"\d{1,2}|" + "|".join(NUMBER_WORDS)
_MENTION = re.compile(
    rf"(?P<plus_before>\+\s*)?\b(?P<n>{_NUMBER})\b\s*(?P<plus>\+)?\s*"
    rf"(?P<range>(?:-|–|—|to)\s*(?:{_NUMBER})\s*\+?\s*)?(?:years?|yrs?)\b['’]?",
    re.I)
_CLAUSE_BREAK = re.compile(r"[\n.;!?•]|\s-\s")
_EXPERIENCE_AFTER = re.compile(r"^\s*\+?\s*(?:of\s+)?(?:[\w&/'’-]+\s+){0,4}?(?:experience|expertise|track record)\b", re.I)
_FOLLOWER = re.compile(r"^\s*\)?\s*(?:(?:of|in|as|within|across|on|at|minimum|min\.?|or more|and above|"
                       r"professional|relevant|hands-on|practical|industry|work)\b|(?:\w+ly\s+)?[a-z]+ing\b)", re.I)
_CUE_BEFORE = re.compile(r"(?:at least|minimum(?: of)?|min\.?|you have|have|having|with|bring|requires?|"
                         r"required|need(?:s|ed)?|approximately|ca\.|experience:|experience \()\s*$", re.I)
_LINE_START = re.compile(r"^[\s\-–—*•·>]*$")
_NEGATIVE = re.compile(
    r"\b(?:history|founded|established|anniversary|for over|over the (?:last|past)|next\s+\S+\s+years|"
    r"years running|of service|sabbatical|retain(?:ed)?|kept for|stored|warranty|years? old|year olds|ago|"
    r"in business|on the market|ha(?:s|ve) helped|ha(?:s|ve) empowered|we have been)\b", re.I)
_PREFERENCE = re.compile(r"\b(?:preferred|nice to have|ideally|a plus|bonus|advantage(?:ous)?)\b", re.I)


def _value(token: str) -> int:
    token = token.lower()
    return NUMBER_WORDS[token] if token in NUMBER_WORDS else int(token)


def _clause(text: str, start: int, end: int) -> tuple[str, str]:
    """The text before and after a mention, cut at the clause boundaries."""
    before = text[max(0, start - 120):start]
    after = text[end:end + 120]
    breaks = list(_CLAUSE_BREAK.finditer(before))
    before = before[breaks[-1].end():] if breaks else before
    cut = _CLAUSE_BREAK.search(after)
    return before, after[:cut.start()] if cut else after


@dataclass(frozen=True)
class YearsMention:
    years: int
    start: int


def requirement_mentions(text: str) -> list[YearsMention]:
    mentions = []
    for match in _MENTION.finditer(text or ""):
        years = _value(match["n"])
        if not 1 <= years <= MAX_YEARS:
            continue
        before, after = _clause(text, match.start(), match.end())
        clause = before + match.group(0) + after
        if _NEGATIVE.search(clause) or _PREFERENCE.search(clause):
            continue
        shaped = bool(match["plus"] or match["plus_before"] or match["range"] or _CUE_BEFORE.search(before)
                      or _LINE_START.match(before))
        if _EXPERIENCE_AFTER.match(after) or (shaped and _FOLLOWER.match(after)):
            mentions.append(YearsMention(years, match.start()))
    return mentions


def minimum_required_years(text: str) -> int | None:
    """The first requirement mention of years in a posting, or None (rule in the module docstring)."""
    mentions = requirement_mentions(text)
    return mentions[0].years if mentions else None


# -- periods ----------------------------------------------------------------------------------

def month_index(value: date) -> int:
    return value.year * 12 + value.month - 1


def merged_months(periods: list[tuple[date, date]]) -> int:
    """Months covered by the periods, counting each calendar month once (start and end months included)."""
    spans = sorted((month_index(start), month_index(end)) for start, end in periods if end >= start)
    total, current = 0, None
    for start, end in spans:
        if current and start <= current[1] + 1:  # overlapping or directly adjacent
            current = (current[0], max(current[1], end))
            continue
        if current:
            total += current[1] - current[0] + 1
        current = (start, end)
    return total + (current[1] - current[0] + 1 if current else 0)


# -- ISCO grouping ----------------------------------------------------------------------------

RELEVANCE_DIGITS = 3


def isco_group(code: str | None, digits: int = RELEVANCE_DIGITS) -> str | None:
    """The ISCO group of a unit-group code at `digits` digits (3: "2512" -> "251")."""
    if not code or len(code) < digits or not code[:digits].isdigit():
        return None
    return code[:digits]


@dataclass(frozen=True)
class WorkPeriod:
    start: date
    end: date
    isco_code: str | None


def relevant_months(periods: list[WorkPeriod], job_isco_code: str | None, digits: int = RELEVANCE_DIGITS) -> int:
    """Merged months of the periods whose occupation is in the job's ISCO group."""
    group = isco_group(job_isco_code, digits)
    if group is None:
        return 0
    return merged_months([(p.start, p.end) for p in periods if isco_group(p.isco_code, digits) == group])

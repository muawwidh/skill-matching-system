"""Duplicate postings in the candidate's job list (display only; jobs stay in the database).

Two jobs are the same posting when their titles and companies are identical
(case, punctuation and spacing ignored) and their descriptions are
near-identical: a word-level similarity (difflib ratio) of at least
`MIN_SIMILARITY` (0.95 since 2026-11-27, so different roles are never folded).
Live examples (2026-11-26): the same role published per country differs only
in a pay-transparency or benefits paragraph (0.918-0.995); two different roles
of one company with the same title scored 0.886 and 0.898.

The list keeps the best-ranked posting of each group at its position and lists
the locations of all of them; the order of the remaining jobs is unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

MIN_SIMILARITY = 0.95


def _key(value: str | None) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", (value or "").casefold()).split())


@lru_cache(maxsize=4096)
def description_similarity(first: str, second: str) -> float:
    a, b = _key(first).split(), _key(second).split()
    if a == b:
        return 1.0
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    if matcher.real_quick_ratio() < MIN_SIMILARITY or matcher.quick_ratio() < MIN_SIMILARITY:
        return matcher.quick_ratio()
    return matcher.ratio()


@dataclass
class PostingGroup:
    job: object  # the best-ranked posting, shown
    duplicates: list = field(default_factory=list)  # further postings, in rank order

    @property
    def locations(self) -> list[str]:
        seen: list[str] = []
        for job in [self.job, *self.duplicates]:
            location = (job.location or "").strip()
            if location and location.casefold() not in {item.casefold() for item in seen}:
                seen.append(location)
        return seen


def same_posting(first, second) -> bool:
    return (_key(first.title) == _key(second.title) and _key(first.company) == _key(second.company)
            and description_similarity(first.cleaned_description or first.description or "",
                                       second.cleaned_description or second.description or "") >= MIN_SIMILARITY)


def collapse_duplicates(jobs: list) -> list[PostingGroup]:
    """Ranked jobs -> one group per posting, in the order of each group's best-ranked job."""
    groups: list[PostingGroup] = []
    by_key: dict[tuple[str, str], list[PostingGroup]] = {}
    for job in jobs:
        candidates = by_key.setdefault((_key(job.title), _key(job.company)), [])
        group = next((g for g in candidates if same_posting(g.job, job)), None)
        if group is None:
            group = PostingGroup(job)
            candidates.append(group)
            groups.append(group)
        else:
            group.duplicates.append(job)
    return groups

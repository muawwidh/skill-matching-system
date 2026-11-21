"""ESCO occupations for relevant experience (D060): occupation-only linking and ISCO groups.

Uses the existing linker (`ConceptIndex`: exact preferred/alternative label,
then fuzzy) restricted to active ESCO occupations, and the existing
auto-approval rule (top candidate unique and confidence >= 0.95). Each
occupation's ISCO unit group (4 digits) comes from the ESCO "broader"
relations: directly, or through its parent occupation. Built once per active
taxonomy (same fingerprint as the concept index) and kept in memory.
"""
from __future__ import annotations

import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.taxonomy.concept_index import ConceptIndex, IndexedConcept, _fingerprint
from app.taxonomy.normalization import normalize_taxonomy_text

AUTO_APPROVE_CONFIDENCE = 0.95  # same rule as taxonomy linking (taxonomy_service.link_document)
_SENIORITY = re.compile(r"\b(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|intern|internship|working student|"
                        r"werkstudent|trainee|mid|medior|entry[- ]level|remote|hybrid|full[- ]time|part[- ]time|"
                        r"freelance)\b", re.I)


def clean_title(title: str) -> str:
    """Job-title clean-up before linking: drop bracketed text (e.g. "(m/w/d)"), anything after
    " - ", "|", "/ " or a comma, and seniority/work-mode words."""
    title = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title or "")
    title = re.split(r"\s+[|–—-]\s+|,\s+|/\s+|\s-\s", title)[0]
    return " ".join(_SENIORITY.sub(" ", title).split())


@dataclass(frozen=True)
class OccupationMatch:
    concept_id: UUID
    label: str
    isco_code: str | None
    confidence: float
    method: str


@dataclass(frozen=True)
class OccupationLink:
    match: OccupationMatch | None  # None: occupation not determined
    automatic: bool


class OccupationCatalog:
    def __init__(self, occupations: list[IndexedConcept], alternatives: dict[UUID, set[str]],
                 isco_codes: dict[UUID, str], group_labels: dict[str, str]) -> None:
        self.index = ConceptIndex(occupations, alternatives, max_candidates=5)
        self.labels = {item.id: item.preferred_label for item in occupations}
        self.isco_codes = isco_codes
        self.group_labels = group_labels

    def _matches(self, title: str) -> tuple[list[OccupationMatch], bool]:
        if not normalize_taxonomy_text(title):
            return [], False
        ranked, unique_top = self.index.rank_with_top_uniqueness(title)
        return [OccupationMatch(item.concept.id, item.concept.preferred_label,
                                self.isco_codes.get(item.concept.id), item.confidence, item.method)
                for item in ranked], unique_top

    def suggest(self, title: str, limit: int = 5) -> list[OccupationMatch]:
        """Top occupations for a title: the cleaned title first, then the title as written."""
        seen: dict[UUID, OccupationMatch] = {}
        for variant in (clean_title(title), title):
            for match in self._matches(variant)[0]:
                if match.concept_id not in seen or match.confidence > seen[match.concept_id].confidence:
                    seen[match.concept_id] = match
        ranked = sorted(seen.values(), key=lambda m: (-m.confidence, m.label.casefold(), str(m.concept_id)))
        return ranked[:limit]

    def link_job_title(self, title: str) -> OccupationLink:
        """Automatic occupation of a job title, or not determined (existing auto-approval rule)."""
        matches, unique_top = self._matches(clean_title(title))
        if matches and unique_top and matches[0].confidence >= AUTO_APPROVE_CONFIDENCE:
            return OccupationLink(matches[0], True)
        return OccupationLink(None, False)

    def is_occupation(self, concept_id: UUID) -> bool:
        return concept_id in self.labels

    def describe(self, concept_id: UUID | None) -> dict | None:
        if concept_id is None or concept_id not in self.labels:
            return None
        code = self.isco_codes.get(concept_id)
        return {"concept_id": concept_id, "label": self.labels[concept_id], "isco_code": code,
                "isco_unit_group": self.group_labels.get(code or "", "")}

    def group_label(self, group: str | None) -> str:
        return self.group_labels.get(group or "", "")


def _isco_code(concept_id: UUID, broader: dict[UUID, list[UUID]], groups: dict[UUID, str], depth: int = 0) -> str | None:
    for target in broader.get(concept_id, ()):
        if target in groups:
            return groups[target]
    if depth < 10:
        for target in broader.get(concept_id, ()):
            code = _isco_code(target, broader, groups, depth + 1)
            if code:
                return code
    return None


def _build(db: Session) -> OccupationCatalog:
    from app.db.models import (TaxonomyConcept, TaxonomyLabel, TaxonomyRelationship, TaxonomySource,
                               TaxonomyVersion)

    versions = list(db.scalars(select(TaxonomyVersion.id).join(TaxonomySource, TaxonomySource.id == TaxonomyVersion.source_id)
                               .where(TaxonomySource.code == "ESCO", TaxonomyVersion.status == "active")))
    rows = list(db.execute(select(TaxonomyConcept.id, TaxonomyConcept.taxonomy_version_id, TaxonomyConcept.preferred_label,
                                  TaxonomyConcept.normalized_label, TaxonomyConcept.concept_type, TaxonomyConcept.external_id)
                           .where(TaxonomyConcept.taxonomy_version_id.in_(versions),
                                  TaxonomyConcept.concept_type.in_(["occupation", "isco_group"]))
                           .order_by(TaxonomyConcept.id))) if versions else []
    occupations = [IndexedConcept(r.id, r.taxonomy_version_id, r.preferred_label, r.normalized_label)
                   for r in rows if r.concept_type == "occupation"]
    groups = {r.id: r.external_id.rsplit("/", 1)[-1].lstrip("Cc") for r in rows if r.concept_type == "isco_group"}
    group_labels = {groups[r.id]: r.preferred_label for r in rows if r.concept_type == "isco_group"}
    broader: dict[UUID, list[UUID]] = defaultdict(list)
    if versions:
        for source, target in db.execute(select(TaxonomyRelationship.source_concept_id, TaxonomyRelationship.target_concept_id)
                                         .where(TaxonomyRelationship.relationship_type == "broader",
                                                TaxonomyRelationship.taxonomy_version_id.in_(versions))):
            broader[source].append(target)
    alternatives: dict[UUID, set[str]] = defaultdict(set)
    ids = [item.id for item in occupations]
    if ids:
        for concept_id, label in db.execute(select(TaxonomyLabel.concept_id, TaxonomyLabel.normalized_label)
                                            .where(TaxonomyLabel.concept_id.in_(ids))):
            alternatives[concept_id].add(label)
    codes = {item.id: code for item in occupations if (code := _isco_code(item.id, broader, groups))}
    return OccupationCatalog(occupations, alternatives, codes, group_labels)


_lock = threading.Lock()
_cached: tuple[tuple, OccupationCatalog] | None = None


def occupation_catalog(db: Session) -> OccupationCatalog:
    """The catalog of active ESCO occupations, rebuilt only when the active taxonomy changed."""
    global _cached
    fingerprint = _fingerprint(db)
    with _lock:
        if _cached is not None and _cached[0] == fingerprint:
            return _cached[1]
        catalog = _build(db)
        _cached = (fingerprint, catalog)
        return catalog


def clear_occupation_catalog() -> None:
    global _cached
    with _lock:
        _cached = None

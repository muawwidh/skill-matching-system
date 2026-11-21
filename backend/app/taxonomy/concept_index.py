"""In-memory index of active taxonomy concepts for linking.

Produces exactly the ranking of `TaxonomyLinker.rank_with_top_uniqueness`
(the reference implementation) but:

- holds plain data, not ORM objects, so linking does not load ~190k objects
  into the session for every document;
- is built once and reused until the active taxonomy changes (fingerprint of
  active versions and their concept/label counts);
- looks up exact preferred/alternative labels in dictionaries and scores fuzzy
  candidates with `rapidfuzz.process.extract` over one flat label list;
- memoizes results per normalized term (bounded), because the same terms
  recur across documents (7,192 live job terms had 956 distinct texts).
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from rapidfuzz import process
from rapidfuzz.fuzz import ratio
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.taxonomy.linker import RankedConcept
from app.taxonomy.normalization import normalize_taxonomy_text


@dataclass(frozen=True)
class IndexedConcept:
    """The fields of a concept that linking needs (duck-types `TaxonomyConcept` for `RankedConcept`)."""

    id: UUID
    taxonomy_version_id: UUID
    preferred_label: str
    normalized_label: str


class ConceptIndex:
    def __init__(self, concepts: list[IndexedConcept], alternatives: dict[UUID, set[str]],
                 fuzzy_threshold: float = 0.70, max_candidates: int = 5, cache_size: int = 50_000) -> None:
        self.concepts = concepts
        self.fuzzy_threshold = fuzzy_threshold
        self.max_candidates = max_candidates
        self._preferred: dict[str, list[int]] = {}
        self._alternative: dict[str, list[int]] = {}
        label_owners: dict[str, list[int]] = {}
        for position, concept in enumerate(concepts):
            self._preferred.setdefault(concept.normalized_label, []).append(position)
            labels = alternatives.get(concept.id, set())
            for label in labels:
                self._alternative.setdefault(label, []).append(position)
            # Fuzzy candidates per concept: preferred label and alternative labels.
            for label in {concept.normalized_label, *labels}:
                label_owners.setdefault(label, []).append(position)
        self._choices = list(label_owners)
        self._owners = [label_owners[label] for label in self._choices]
        self._cache: OrderedDict[str, tuple[list[RankedConcept], bool]] = OrderedDict()
        self._cache_size = cache_size
        self._cache_lock = threading.Lock()

    def __len__(self) -> int:
        return len(self.concepts)

    def rank_with_top_uniqueness(self, text: str) -> tuple[list[RankedConcept], bool]:
        normalized = normalize_taxonomy_text(text)
        if not normalized:
            return [], False
        with self._cache_lock:
            cached = self._cache.get(normalized)
            if cached is not None:
                self._cache.move_to_end(normalized)
                return list(cached[0]), cached[1]
        result = self._rank(normalized)
        with self._cache_lock:
            self._cache[normalized] = result
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return list(result[0]), result[1]

    def _rank(self, normalized: str) -> tuple[list[RankedConcept], bool]:
        best: dict[int, RankedConcept] = {}
        for position in self._preferred.get(normalized, ()):
            best[position] = RankedConcept(self.concepts[position], "exact_preferred", 1.0)
        for position in self._alternative.get(normalized, ()):
            if position not in best:
                best[position] = RankedConcept(self.concepts[position], "exact_alternative", 0.98)
        fuzzy: dict[int, float] = {}
        for _, score, choice_position in process.extract(normalized, self._choices, scorer=ratio, processor=None,
                                                         score_cutoff=self.fuzzy_threshold * 100, limit=None):
            for position in self._owners[choice_position]:
                if position not in best and score > fuzzy.get(position, -1.0):
                    fuzzy[position] = score
        for position, score in fuzzy.items():
            # Same arithmetic and threshold as the reference linker.
            fuzzy_score = score / 100
            if fuzzy_score < self.fuzzy_threshold:
                continue
            best[position] = RankedConcept(self.concepts[position], "fuzzy", round(fuzzy_score * 0.94, 4))
        matches = sorted(best.values(), key=lambda item: (
            -item.confidence, item.concept.preferred_label.casefold(),
            str(item.concept.taxonomy_version_id), str(item.concept.id)))
        unique_top = bool(matches) and sum(item.confidence == matches[0].confidence for item in matches) == 1
        return matches[: self.max_candidates], unique_top


# -- process-wide cache ----------------------------------------------------------------------

_index_lock = threading.Lock()
_cached: tuple[tuple, ConceptIndex] | None = None


def _fingerprint(db: Session) -> tuple:
    from app.db.models import TaxonomyConcept, TaxonomyLabel, TaxonomyVersion

    versions = tuple(db.execute(select(TaxonomyVersion.id, TaxonomyVersion.updated_at)
                                .where(TaxonomyVersion.status == "active").order_by(TaxonomyVersion.id)).all())
    active = select(TaxonomyVersion.id).where(TaxonomyVersion.status == "active")
    concepts = db.scalar(select(func.count()).select_from(TaxonomyConcept)
                         .where(TaxonomyConcept.taxonomy_version_id.in_(active)))
    labels = db.scalar(select(func.count()).select_from(TaxonomyLabel).join(TaxonomyConcept)
                       .where(TaxonomyConcept.taxonomy_version_id.in_(active)))
    return versions, concepts, labels


def _build(db: Session) -> ConceptIndex:
    from app.db.models import TaxonomyConcept, TaxonomyLabel, TaxonomyVersion

    active = select(TaxonomyVersion.id).where(TaxonomyVersion.status == "active")
    concepts = [IndexedConcept(*row) for row in db.execute(
        select(TaxonomyConcept.id, TaxonomyConcept.taxonomy_version_id, TaxonomyConcept.preferred_label,
               TaxonomyConcept.normalized_label)
        .where(TaxonomyConcept.taxonomy_version_id.in_(active)).order_by(TaxonomyConcept.id))]
    alternatives: dict[UUID, set[str]] = {}
    for concept_id, label in db.execute(
            select(TaxonomyLabel.concept_id, TaxonomyLabel.normalized_label).join(TaxonomyConcept)
            .where(TaxonomyConcept.taxonomy_version_id.in_(active))):
        alternatives.setdefault(concept_id, set()).add(label)
    return ConceptIndex(concepts, alternatives)


def active_concept_index(db: Session) -> ConceptIndex:
    """The index of active concepts, rebuilt only when the active taxonomy changed."""
    global _cached
    fingerprint = _fingerprint(db)
    with _index_lock:
        if _cached is not None and _cached[0] == fingerprint:
            return _cached[1]
        index = _build(db)
        _cached = (fingerprint, index)
        return index


def clear_concept_index_cache() -> None:
    global _cached
    with _index_lock:
        _cached = None

from dataclasses import dataclass

from rapidfuzz.fuzz import ratio

from app.db.models import TaxonomyConcept
from app.taxonomy.normalization import normalize_taxonomy_text


@dataclass(frozen=True)
class RankedConcept:
    concept: TaxonomyConcept
    method: str
    confidence: float


class TaxonomyLinker:
    def __init__(self, fuzzy_threshold: float = 0.70, max_candidates: int = 5) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.max_candidates = max_candidates

    def rank(self, text: str, concepts: list[TaxonomyConcept]) -> list[RankedConcept]:
        ranked, _ = self.rank_with_top_uniqueness(text, concepts)
        return ranked

    def rank_with_top_uniqueness(
        self, text: str, concepts: list[TaxonomyConcept]
    ) -> tuple[list[RankedConcept], bool]:
        normalized = normalize_taxonomy_text(text)
        if not normalized:
            return [], False
        best_by_concept: dict[tuple, RankedConcept] = {}
        for concept in concepts:
            preferred = concept.normalized_label
            if normalized == preferred:
                match = RankedConcept(concept, "exact_preferred", 1.0)
            else:
                alternative_labels = {label.normalized_label for label in concept.labels}
                if normalized in alternative_labels:
                    match = RankedConcept(concept, "exact_alternative", 0.98)
                else:
                    candidates = [preferred, *alternative_labels]
                    fuzzy_score = max((ratio(normalized, label) / 100 for label in candidates), default=0.0)
                    if fuzzy_score < self.fuzzy_threshold:
                        continue
                    match = RankedConcept(concept, "fuzzy", round(fuzzy_score * 0.94, 4))
            identity = (concept.taxonomy_version_id, concept.id)
            previous = best_by_concept.get(identity)
            if previous is None or match.confidence > previous.confidence:
                best_by_concept[identity] = match
        matches = sorted(
            best_by_concept.values(),
            key=lambda item: (
                -item.confidence, item.concept.preferred_label.casefold(),
                str(item.concept.taxonomy_version_id), str(item.concept.id),
            ),
        )
        unique_top = bool(matches) and sum(item.confidence == matches[0].confidence for item in matches) == 1
        return matches[: self.max_candidates], unique_top

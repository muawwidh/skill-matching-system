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
        normalized = normalize_taxonomy_text(text)
        if not normalized:
            return []
        matches: list[RankedConcept] = []
        for concept in concepts:
            preferred = concept.normalized_label
            if normalized == preferred:
                matches.append(RankedConcept(concept, "exact_preferred", 1.0))
                continue
            alternative_labels = {label.normalized_label for label in concept.labels}
            if normalized in alternative_labels:
                matches.append(RankedConcept(concept, "exact_alternative", 0.98))
                continue
            candidates = [preferred, *alternative_labels]
            fuzzy_score = max((ratio(normalized, label) / 100 for label in candidates), default=0.0)
            if fuzzy_score >= self.fuzzy_threshold:
                matches.append(RankedConcept(concept, "fuzzy", round(fuzzy_score * 0.94, 4)))
        matches.sort(key=lambda item: (-item.confidence, item.concept.preferred_label.casefold()))
        return matches[: self.max_candidates]

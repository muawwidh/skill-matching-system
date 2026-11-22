import type { Occupation, OccupationSuggestion } from "../types/experience";
import type { TaxonomyConcept } from "../types/taxonomy";

/** Same threshold as automatic approval of taxonomy links. */
export const STRONG_MATCH = 0.95;

/** The suggestion to preselect: the first one, only when it is a strong string match. Otherwise none. */
export function preselectedOccupation(suggestions: OccupationSuggestion[]): OccupationSuggestion | undefined {
  const first = suggestions[0];
  return first && first.method !== "embedding" && first.confidence >= STRONG_MATCH ? first : undefined;
}

/**
 * Taxonomy search results (ESCO occupations of the active release) as occupations, best wording match first:
 * name starts with the query, then name contains it, then a match on another label; shorter names first.
 */
export function occupationSearchResults(concepts: TaxonomyConcept[], query: string, limit = 8): Occupation[] {
  const q = query.trim().toLowerCase();
  const seen = new Set<string>();
  const rank = (label: string) => (label.startsWith(q) ? 0 : label.includes(q) ? 1 : 2);
  return concepts
    .filter((concept) => concept.concept_type === "occupation" && !seen.has(concept.id) && seen.add(concept.id))
    .map((concept) => ({ concept, label: concept.preferred_label.toLowerCase() }))
    .sort((a, b) => rank(a.label) - rank(b.label) || a.label.length - b.label.length || a.label.localeCompare(b.label))
    .slice(0, limit)
    .map(({ concept }) => ({ concept_id: concept.id, label: concept.preferred_label, isco_code: null, isco_unit_group: "" }));
}

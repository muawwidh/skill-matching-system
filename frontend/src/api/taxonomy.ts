import { apiRequest } from "./client";
import type {
  EscoOnetMapping,
  TaxonomyConcept,
  TaxonomyImportResult,
  TaxonomyLinkCandidate,
  TaxonomyVersion,
  TaxonomyReviewGroup,
  TaxonomyReviewEvent,
} from "../types/taxonomy";

export function listTaxonomyVersions(accessToken: string) {
  return apiRequest<TaxonomyVersion[]>("/taxonomy/versions", { accessToken });
}

export function searchTaxonomy(
  accessToken: string,
  query: string,
  filters: { source?: string; conceptType?: string; limit?: number } = {},
) {
  const params = new URLSearchParams({ q: query });
  if (filters.source) params.set("source", filters.source);
  if (filters.conceptType) params.set("concept_type", filters.conceptType);
  if (filters.limit) params.set("limit", String(filters.limit));
  return apiRequest<TaxonomyConcept[]>(`/taxonomy/search?${params}`, { accessToken });
}

export function listTaxonomyMappings(accessToken: string) {
  return apiRequest<EscoOnetMapping[]>("/taxonomy/mappings", { accessToken });
}

export function listPendingTaxonomyLinks(accessToken: string) {
  return apiRequest<TaxonomyLinkCandidate[]>("/admin/mappings/review?scope=default", { accessToken });
}

export function importBundledTaxonomySample(accessToken: string) {
  return apiRequest<TaxonomyImportResult[]>("/taxonomy/import/sample", {
    method: "POST",
    accessToken,
  });
}

export function importTaxonomyRelease(
  accessToken: string,
  source: "esco" | "onet" | "mappings",
  file: File,
  version: string,
  releaseDate: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("version", version);
  if (source !== "mappings") {
    formData.append("release_date", releaseDate);
  }
  return apiRequest<TaxonomyImportResult>(`/taxonomy/import/${source}`, {
    method: "POST",
    accessToken,
    body: formData,
  });
}

export function reviewTaxonomyLink(
  accessToken: string,
  candidateId: string,
  status: "approved" | "rejected",
  replaceSelection = false,
  expectedSelectionToken: string | null = null,
) {
  return apiRequest<TaxonomyLinkCandidate>(`/taxonomy/link/${candidateId}/approve`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ status, replace_selection: replaceSelection, expected_selection_token: expectedSelectionToken }),
  });
}

export type TaxonomyReviewScope = "default" | "live" | "all";

export function listTaxonomyReviews(accessToken: string, state: string, query: string, offset: number,
                                    scope: TaxonomyReviewScope = "default") {
  const params = new URLSearchParams({ state, q: query, offset: String(offset), limit: "20", scope });
  return apiRequest<{ items: TaxonomyReviewGroup[]; has_more: boolean }>(`/taxonomy/reviews?${params}`, { accessToken });
}

export function listTaxonomyReviewHistory(accessToken: string, source: string, termId: string, offset: number) {
  return apiRequest<TaxonomyReviewEvent[]>(`/taxonomy/reviews/${source}/${termId}/history?offset=${offset}&limit=20`, { accessToken });
}

/** A candidate's own CV skills: taxonomy suggestions and current selection (D048). */
export function listMyCvTaxonomyLinks(accessToken: string, cvId: string) {
  return apiRequest<TaxonomyReviewGroup[]>(`/cvs/${cvId}/taxonomy-links`, { accessToken });
}

export function reviewMyCvTaxonomyLink(
  accessToken: string,
  cvId: string,
  candidateId: string,
  status: "approved" | "rejected",
  selectionToken?: string,
) {
  return apiRequest<TaxonomyLinkCandidate>(`/cvs/${cvId}/taxonomy-links/${candidateId}`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({
      status,
      replace_selection: Boolean(selectionToken),
      expected_selection_token: selectionToken ?? null,
    }),
  });
}

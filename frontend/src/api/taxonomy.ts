import { apiRequest } from "./client";
import type {
  EscoOnetMapping,
  TaxonomyConcept,
  TaxonomyImportResult,
  TaxonomyLinkCandidate,
  TaxonomyVersion,
} from "../types/taxonomy";

export function listTaxonomyVersions(accessToken: string) {
  return apiRequest<TaxonomyVersion[]>("/taxonomy/versions", { accessToken });
}

export function searchTaxonomy(accessToken: string, query: string) {
  return apiRequest<TaxonomyConcept[]>(`/taxonomy/search?q=${encodeURIComponent(query)}`, {
    accessToken,
  });
}

export function listTaxonomyMappings(accessToken: string) {
  return apiRequest<EscoOnetMapping[]>("/taxonomy/mappings", { accessToken });
}

export function listPendingTaxonomyLinks(accessToken: string) {
  return apiRequest<TaxonomyLinkCandidate[]>("/admin/mappings/review", { accessToken });
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
) {
  return apiRequest<TaxonomyLinkCandidate>(`/taxonomy/link/${candidateId}/approve`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ status }),
  });
}

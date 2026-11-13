import { ApiError, apiRequest } from "./client";
import type { CandidateInputs, FactBody, GroupBody, InventoryBody, JobInputs, MatchingRun, Classification, Review } from "../types/matching";

async function matchingRequest<T>(...args: Parameters<typeof apiRequest<T>>): Promise<T> {
  try {
    return await apiRequest<T>(...args);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const message = error.message.trim();
      const separator = /[.!?]$/.test(message) ? " " : ". ";
      throw new ApiError(`${message}${separator}Reload current inputs before trying again; the request was not retried.`, error.status);
    }
    throw error;
  }
}

export const currentRun = (token: string) => matchingRequest<MatchingRun>("/matching-runs/current", { accessToken: token });
export const createRun = (token: string) => matchingRequest<MatchingRun>("/matching-runs", { method: "POST", accessToken: token, body: "{}" });
export const ownProfile = (token: string) => apiRequest<{ id: string }>("/candidates/me", { accessToken: token });
export const candidateInputs = (token: string, id: string) => matchingRequest<CandidateInputs>(`/matching-inputs/candidates/${id}/facts`, { accessToken: token });
export const jobInputs = (token: string, id: string) => matchingRequest<JobInputs>(`/matching-inputs/jobs/${id}/inventory`, { accessToken: token });

export function inputWriter(token: string, scope: "candidates" | "jobs", id: string, fingerprint: string) {
  const base = `/matching-inputs/${scope}/${encodeURIComponent(id)}`;
  const write = (path: string, method: string, body: object) => matchingRequest<unknown>(base + path, {
    method, accessToken: token, body: JSON.stringify({ ...body, expected_fingerprint: fingerprint }),
  });
  return {
    fact: (body: FactBody) => write("/facts", "POST", body),
    remove: (kind: "facts" | "groups", itemId: string) => matchingRequest<unknown>(`${base}/${kind}/${encodeURIComponent(itemId)}?expected_fingerprint=${encodeURIComponent(fingerprint)}`, { method: "DELETE", accessToken: token }),
    group: (body: GroupBody) => write("/groups", "POST", body),
    classify: (skill: string, classification: Classification, review_status: Review, reason: string) => write(`/occurrences/${encodeURIComponent(skill)}`, "PUT", { classification, review_status, reason }),
    inventory: (body: InventoryBody) => write("/inventory", "PUT", body),
  };
}

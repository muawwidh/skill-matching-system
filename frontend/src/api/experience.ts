import { apiRequest } from "./client";
import type { DetectedWorkEntry, OccupationSuggestion, WorkEntry, WorkEntryPayload } from "../types/experience";

const BASE = "/candidates/me/work-entries";

export function listWorkEntries(accessToken: string) {
  return apiRequest<WorkEntry[]>(BASE, { accessToken });
}

export function listDetectedWorkEntries(accessToken: string) {
  return apiRequest<DetectedWorkEntry[]>(`${BASE}/detected`, { accessToken });
}

export function createWorkEntry(accessToken: string, payload: WorkEntryPayload) {
  return apiRequest<WorkEntry>(BASE, { method: "POST", accessToken, body: JSON.stringify(payload) });
}

export function updateWorkEntry(accessToken: string, id: string, payload: WorkEntryPayload) {
  return apiRequest<WorkEntry>(`${BASE}/${id}`, { method: "PUT", accessToken, body: JSON.stringify(payload) });
}

export function deleteWorkEntry(accessToken: string, id: string) {
  return apiRequest<void>(`${BASE}/${id}`, { method: "DELETE", accessToken });
}

export function suggestOccupations(accessToken: string, title: string) {
  return apiRequest<OccupationSuggestion[]>(`${BASE}/occupation-suggestions?title=${encodeURIComponent(title)}`, {
    accessToken,
  });
}

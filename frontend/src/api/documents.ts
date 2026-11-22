import { apiRequest } from "./client";
import type {
  CandidateSkill,
  CandidateSkillGroup,
  CvDocument,
  Job,
  JobPayload,
  JobPool,
  JobSkill,
  MatchingProfile,
  ProcessingLog,
  RecommendationList,
  SkillGaps,
  SystemOverview,
} from "../types/documents";

export function pasteCv(accessToken: string, text: string, consentToProcess: boolean) {
  return apiRequest<CvDocument>("/cvs/paste", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      text,
      original_filename: "pasted-cv.txt",
      consent_to_process: consentToProcess,
    }),
  });
}

export function uploadCv(accessToken: string, file: File, consentToProcess: boolean) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("consent_to_process", String(consentToProcess));
  return apiRequest<CvDocument>("/cvs/upload", {
    method: "POST",
    accessToken,
    body: formData,
  });
}

export function listCvs(accessToken: string) {
  return apiRequest<CvDocument[]>("/cvs", { accessToken });
}

/** Delete a CV; `removeWorkEntries` also removes the work entries taken from it (manual ones always stay). */
export function deleteCv(accessToken: string, cvId: string, removeWorkEntries: boolean) {
  return apiRequest<void>(`/cvs/${cvId}?remove_work_entries=${removeWorkEntries}`, { method: "DELETE", accessToken });
}

export function getMatchingProfile(accessToken: string) {
  return apiRequest<MatchingProfile>("/candidates/me/matching-profile", { accessToken });
}

export function createJob(accessToken: string, payload: JobPayload) {
  return apiRequest<Job>("/jobs", {
    method: "POST",
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function listJobs(accessToken: string) {
  return apiRequest<Job[]>("/jobs", { accessToken });
}

export function archiveJob(accessToken: string, jobId: string) {
  return apiRequest<Job>(`/jobs/${jobId}/archive`, {
    method: "POST",
    accessToken,
  });
}

export function listProcessingLogs(accessToken: string) {
  return apiRequest<ProcessingLog[]>("/admin/logs", { accessToken });
}

export function listCvSkills(accessToken: string, cvId: string) {
  return apiRequest<CandidateSkill[]>(`/cvs/${cvId}/extracted-skills`, { accessToken });
}

export function listCvSkillGroups(accessToken: string, cvId: string) {
  return apiRequest<CandidateSkillGroup[]>(`/cvs/${cvId}/skill-groups`, { accessToken });
}

export function reviewCvSkills(accessToken: string, cvId: string, skills: CandidateSkill[]) {
  return apiRequest<CandidateSkill[]>(`/cvs/${cvId}/extracted-skills`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({
      skills: skills.map((skill) => ({
        id: skill.id,
        raw_text: skill.raw_text,
        normalized_text: skill.normalized_text,
        skill_type: skill.skill_type,
        evidence_sentence: skill.evidence_sentence,
        review_status: skill.review_status,
      })),
    }),
  });
}

export function listJobSkills(accessToken: string, jobId: string) {
  return apiRequest<JobSkill[]>(`/jobs/${jobId}/extracted-skills`, { accessToken });
}

/** Page sizes offered on the Jobs page (D059). */
export const RECOMMENDATION_PAGE_SIZES = [10, 25, 50] as const;

export function listRecommendations(accessToken: string, page = 1, pageSize = 10) {
  return apiRequest<RecommendationList>(`/matches/recommendations?page=${page}&page_size=${pageSize}`, { accessToken });
}

export function refreshRecommendations(accessToken: string, page = 1, pageSize = 10) {
  return apiRequest<RecommendationList>(`/matches/recommendations/refresh?page=${page}&page_size=${pageSize}`, {
    method: "POST",
    accessToken,
  });
}

export function setHideBelowExperience(accessToken: string, value: boolean) {
  return apiRequest<{ hide_below_experience: boolean }>("/matches/preferences", {
    method: "PUT",
    accessToken,
    body: JSON.stringify({ hide_below_experience: value }),
  });
}

export function getSkillGaps(accessToken: string) {
  return apiRequest<SkillGaps>("/matches/skill-gaps", { accessToken });
}

export function getJobPool(accessToken: string) {
  return apiRequest<JobPool>("/matches/job-pool", { accessToken });
}

/** Skills the candidate added by hand. */
export function listManualSkills(accessToken: string) {
  return apiRequest<CandidateSkill[]>("/candidates/me/manual-skills", { accessToken });
}

export function getSystemOverview(accessToken: string) {
  return apiRequest<SystemOverview>("/admin/overview", { accessToken });
}

// Per-occurrence job skill review (admin/researcher only; enforced by the API).
export function reviewJobSkill(accessToken: string, jobId: string, skill: JobSkill, reviewStatus: "approved" | "rejected") {
  return apiRequest<JobSkill>(`/jobs/${jobId}/extracted-skills/${skill.id}`, {
    method: "PUT",
    accessToken,
    body: JSON.stringify({
      raw_text: skill.raw_text,
      normalized_text: skill.normalized_text,
      skill_type: skill.skill_type,
      requirement_type: skill.requirement_type,
      evidence_sentence: skill.evidence_sentence,
      review_status: reviewStatus,
    }),
  });
}

export type JobImportRun = {
  status: string;
  created_at: string;
  finished_at?: string;
  fetched?: number;
  selected?: number;
  outcomes?: Record<string, number>;
  skipped_language?: Record<string, number>;
  skipped_location?: number;
  archived_not_seen?: number;
  archived_over_cap?: number;
  archived_over_source_share?: number;
  over_source_share_not_imported?: number;
  active_live_jobs_by_source?: Record<string, number>;
  active_live_jobs?: number;
  sources?: Record<string, { fetched: number; requests: number; errors: string[] }>;
};

export function getJobImportStatus(accessToken: string) {
  return apiRequest<{ running: boolean; runs: JobImportRun[] }>("/admin/job-import", { accessToken });
}

export function startJobImport(accessToken: string) {
  return apiRequest<{ started: boolean }>("/admin/job-import", { method: "POST", accessToken });
}

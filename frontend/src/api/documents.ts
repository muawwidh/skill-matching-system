import { apiRequest } from "./client";
import type {
  CandidateSkill,
  CandidateJobMatch,
  CvDocument,
  Job,
  JobPayload,
  JobSkill,
  ProcessingLog,
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

export function listRecommendations(accessToken: string) {
  return apiRequest<CandidateJobMatch[]>("/matches/recommendations", { accessToken });
}

export function refreshRecommendations(accessToken: string) {
  return apiRequest<CandidateJobMatch[]>("/matches/recommendations/refresh", {
    method: "POST",
    accessToken,
  });
}

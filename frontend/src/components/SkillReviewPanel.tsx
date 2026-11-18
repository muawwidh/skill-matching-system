import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, X } from "lucide-react";
import { useState } from "react";

import { listJobSkills, reviewJobSkill } from "../api/documents";
import type { JobSkill } from "../types/documents";
import { CandidateSkillGroups, skillSourceLabel } from "./CandidateSkillGroups";

type SkillReviewPanelProps = {
  accessToken: string;
  ownerId: string;
  ownerType: "cv" | "job";
  /** Job skills only: show per-occurrence approve/reject (admin and researcher). */
  canReview?: boolean;
};

export function SkillReviewPanel({ accessToken, ownerId, ownerType, canReview = false }: SkillReviewPanelProps) {
  return ownerType === "cv"
    ? <CandidateSkillGroups key={ownerId} accessToken={accessToken} cvId={ownerId} />
    : <JobSkillGroups accessToken={accessToken} jobId={ownerId} canReview={canReview} />;
}

const REQUIREMENT_STRENGTH: Record<string, number> = { required: 3, preferred: 2, unknown: 1 };

type JobSkillGroup = { key: string; label: string; skillType: string; requirement: string; occurrences: JobSkill[] };

// Display-only grouping of repeated extractions; each occurrence keeps its own row, status and evidence.
function groupJobSkills(skills: JobSkill[]): JobSkillGroup[] {
  const groups = new Map<string, JobSkillGroup>();
  for (const skill of skills) {
    const key = `${skill.normalized_text}::${skill.skill_type}`;
    const group = groups.get(key) ?? { key, label: skill.raw_text, skillType: skill.skill_type, requirement: "unknown", occurrences: [] };
    group.occurrences.push(skill);
    if ((REQUIREMENT_STRENGTH[skill.requirement_type] ?? 0) > (REQUIREMENT_STRENGTH[group.requirement] ?? 0)) {
      group.requirement = skill.requirement_type;
    }
    groups.set(key, group);
  }
  return [...groups.values()];
}

const sectionLabel = (section: string) => section.replace(/_/g, " ").replace(/^full text$/, "untitled text");

// Distinct detected sections of a group's occurrences, in first-seen order.
function sectionList(occurrences: JobSkill[]): string {
  return [...new Set(occurrences.map((item) => item.source_section).filter(Boolean) as string[])].map(sectionLabel).join(", ");
}

function reviewSummary(occurrences: JobSkill[]): string {
  const counts = occurrences.reduce<Record<string, number>>((result, item) => {
    result[item.review_status] = (result[item.review_status] ?? 0) + 1;
    return result;
  }, {});
  const entries = Object.entries(counts);
  return entries.length === 1 ? entries[0][0] : entries.map(([status, count]) => `${count} ${status}`).join(" · ");
}

function JobSkillGroups({ accessToken, jobId, canReview }: { accessToken: string; jobId: string; canReview: boolean }) {
  const queryClient = useQueryClient();
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const skillQuery = useQuery({
    queryKey: ["job", jobId, "skills"],
    queryFn: () => listJobSkills(accessToken, jobId),
  });
  const review = useMutation({
    mutationFn: ({ skill, status }: { skill: JobSkill; status: "approved" | "rejected" }) =>
      reviewJobSkill(accessToken, jobId, skill, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId, "skills"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  if (skillQuery.isLoading) {
    return <p className="text-sm text-slate-500">Loading extracted skills...</p>;
  }
  const groups = groupJobSkills(skillQuery.data ?? []);
  if (groups.length === 0) {
    return <p className="text-sm text-slate-500">No skills or indicators extracted yet.</p>;
  }

  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-white p-3">
      <h3 className="mb-3 text-sm font-semibold text-ink">Extracted Skills and Indicators</h3>
      {review.error ? <p role="alert" className="mb-2 text-sm text-red-700">{review.error.message}</p> : null}
      <div className="space-y-2">
        {groups.map((group) => {
          const statuses = new Set(group.occurrences.map((item) => item.review_status));
          const withEvidence = group.occurrences.filter((item) => item.evidence_sentence);
          return (
            <article key={group.key} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{group.label}</span>
                <span className="rounded bg-amber-100 px-2 py-1 text-xs text-ember">{group.skillType.replace(/_/g, " ")}</span>
                <span className="rounded bg-slate-200 px-2 py-1 text-xs text-slate-700" title="Strongest requirement type among occurrences">
                  {group.requirement}
                </span>
                <span className="text-xs text-slate-500">
                  {group.occurrences.length} occurrence{group.occurrences.length === 1 ? "" : "s"}
                  {sectionList(group.occurrences) ? ` · from ${sectionList(group.occurrences)}` : ""}
                </span>
                <span className="rounded bg-white px-2 py-1 text-xs text-slate-600">
                  {statuses.size > 1 ? `Mixed: ${reviewSummary(group.occurrences)}` : reviewSummary(group.occurrences)}
                </span>
              </div>
              {withEvidence.length || canReview ? (
                <div className="mt-2">
                  <button
                    className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600"
                    onClick={() => setExpandedEvidence((current) => ({ ...current, [group.key]: !current[group.key] }))}
                    type="button"
                  >
                    {expandedEvidence[group.key] ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                    {canReview ? "Evidence and review" : "Evidence"}
                  </button>
                  {expandedEvidence[group.key] ? (
                    <ul className="mt-2 space-y-2">
                      {group.occurrences.map((item) => (
                        <li key={item.id} className="rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-600">
                          <p className="mb-1 text-xs text-slate-500">
                            {item.raw_text} · {item.requirement_type}{item.source_section ? ` · ${sectionLabel(item.source_section)}` : ""} · {skillSourceLabel(item.source)} · {item.review_status}
                          </p>
                          {item.evidence_sentence || "No evidence text"}
                          {canReview ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                aria-label={`Approve job skill occurrence ${item.id}`}
                                aria-pressed={item.review_status === "approved"}
                                className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium ${
                                  item.review_status === "approved" ? "border-ocean bg-ocean text-white" : "border-slate-300 text-ocean"
                                }`}
                                disabled={review.isPending || item.review_status === "approved"}
                                onClick={() => review.mutate({ skill: item, status: "approved" })}
                                type="button"
                              >
                                <Check size={14} aria-hidden="true" />
                                Approve
                              </button>
                              <button
                                aria-label={`Reject job skill occurrence ${item.id}`}
                                aria-pressed={item.review_status === "rejected"}
                                className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium ${
                                  item.review_status === "rejected" ? "border-red-700 bg-red-700 text-white" : "border-slate-300 text-red-700"
                                }`}
                                disabled={review.isPending || item.review_status === "rejected"}
                                onClick={() => review.mutate({ skill: item, status: "rejected" })}
                                type="button"
                              >
                                <X size={14} aria-hidden="true" />
                                Reject
                              </button>
                            </div>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}

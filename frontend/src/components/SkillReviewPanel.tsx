import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { listJobSkills } from "../api/documents";
import type { JobSkill } from "../types/documents";
import { CandidateSkillGroups, skillSourceLabel } from "./CandidateSkillGroups";

type SkillReviewPanelProps = {
  accessToken: string;
  ownerId: string;
  ownerType: "cv" | "job";
};

export function SkillReviewPanel({ accessToken, ownerId, ownerType }: SkillReviewPanelProps) {
  return ownerType === "cv"
    ? <CandidateSkillGroups key={ownerId} accessToken={accessToken} cvId={ownerId} />
    : <JobSkillGroups accessToken={accessToken} jobId={ownerId} />;
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

function reviewSummary(occurrences: JobSkill[]): string {
  const counts = occurrences.reduce<Record<string, number>>((result, item) => {
    result[item.review_status] = (result[item.review_status] ?? 0) + 1;
    return result;
  }, {});
  const entries = Object.entries(counts);
  return entries.length === 1 ? entries[0][0] : entries.map(([status, count]) => `${count} ${status}`).join(" · ");
}

function JobSkillGroups({ accessToken, jobId }: { accessToken: string; jobId: string }) {
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const skillQuery = useQuery({
    queryKey: ["job", jobId, "skills"],
    queryFn: () => listJobSkills(accessToken, jobId),
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
                </span>
                <span className="rounded bg-white px-2 py-1 text-xs text-slate-600">
                  {statuses.size > 1 ? `Mixed: ${reviewSummary(group.occurrences)}` : reviewSummary(group.occurrences)}
                </span>
              </div>
              {withEvidence.length ? (
                <div className="mt-2">
                  <button
                    className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600"
                    onClick={() => setExpandedEvidence((current) => ({ ...current, [group.key]: !current[group.key] }))}
                    type="button"
                  >
                    {expandedEvidence[group.key] ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                    Evidence
                  </button>
                  {expandedEvidence[group.key] ? (
                    <ul className="mt-2 space-y-2">
                      {group.occurrences.map((item) => (
                        <li key={item.id} className="rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-600">
                          <p className="mb-1 text-xs text-slate-500">
                            {item.raw_text} · {item.requirement_type} · {skillSourceLabel(item.source)} · {item.review_status}
                          </p>
                          {item.evidence_sentence || "No evidence text"}
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

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronRight, X } from "lucide-react";
import { useEffect, useState } from "react";

import { listCvSkills, listJobSkills, reviewCvSkills } from "../api/documents";
import type { CandidateSkill, JobSkill } from "../types/documents";

type SkillReviewPanelProps = {
  accessToken: string;
  ownerId: string;
  ownerType: "cv" | "job";
};

export function SkillReviewPanel({ accessToken, ownerId, ownerType }: SkillReviewPanelProps) {
  const queryClient = useQueryClient();
  const [candidateSkills, setCandidateSkills] = useState<CandidateSkill[]>([]);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});

  const skillQuery = useQuery({
    queryKey: [ownerType, ownerId, "skills"],
    queryFn: () =>
      ownerType === "cv"
        ? listCvSkills(accessToken, ownerId)
        : listJobSkills(accessToken, ownerId),
  });

  useEffect(() => {
    if (ownerType === "cv" && skillQuery.data) {
      setCandidateSkills(skillQuery.data as CandidateSkill[]);
    }
  }, [ownerType, skillQuery.data]);

  const reviewMutation = useMutation({
    mutationFn: () => reviewCvSkills(accessToken, ownerId, candidateSkills),
    onSuccess: (skills) => {
      setCandidateSkills(skills);
      queryClient.invalidateQueries({ queryKey: [ownerType, ownerId, "skills"] });
    },
  });

  const skills = skillQuery.data ?? [];

  if (skillQuery.isLoading) {
    return <p className="text-sm text-slate-500">Loading extracted skills...</p>;
  }

  if (skills.length === 0) {
    return <p className="text-sm text-slate-500">No skills or indicators extracted yet.</p>;
  }

  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-white p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">Extracted Skills and Indicators</h3>
        {ownerType === "cv" ? (
          <button
            className="rounded-md bg-ocean px-3 py-1.5 text-sm font-medium text-white"
            onClick={() => reviewMutation.mutate()}
            type="button"
          >
            Save review
          </button>
        ) : null}
      </div>

      <div className="space-y-2">
        {(ownerType === "cv" ? candidateSkills : (skills as JobSkill[])).map((skill, index) => (
          <article key={skill.id} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              {ownerType === "cv" ? (
                <input
                  className="min-w-36 rounded border border-slate-300 px-2 py-1 text-sm"
                  onChange={(event) =>
                    setCandidateSkills((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index
                          ? { ...item, raw_text: event.target.value, normalized_text: event.target.value.toLowerCase() }
                          : item,
                      ),
                    )
                  }
                  value={skill.raw_text}
                />
              ) : (
                <span className="font-medium text-ink">{skill.raw_text}</span>
              )}
              <span className="rounded bg-amber-100 px-2 py-1 text-xs text-ember">
                {skill.skill_type.replace(/_/g, " ")}
              </span>
              {ownerType === "job" ? (
                <span className="rounded bg-slate-200 px-2 py-1 text-xs text-slate-700">
                  {(skill as JobSkill).requirement_type}
                </span>
              ) : null}
              <span className="text-xs text-slate-500">
                {Math.round(skill.confidence_score * 100)}%
              </span>
              <span className="rounded bg-white px-2 py-1 text-xs text-slate-600">
                {skill.review_status}
              </span>
            </div>
            {skill.evidence_sentence ? (
              <div className="mt-2">
                <button
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600"
                  onClick={() =>
                    setExpandedEvidence((current) => ({
                      ...current,
                      [skill.id]: !current[skill.id],
                    }))
                  }
                  type="button"
                >
                  {expandedEvidence[skill.id] ? (
                    <ChevronDown size={14} aria-hidden="true" />
                  ) : (
                    <ChevronRight size={14} aria-hidden="true" />
                  )}
                  Evidence
                </button>
                {expandedEvidence[skill.id] ? (
                  <p className="mt-2 rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-600">
                    {skill.evidence_sentence}
                  </p>
                ) : null}
              </div>
            ) : null}
            {ownerType === "cv" ? (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-medium ${
                    skill.review_status === "approved"
                      ? "border-ocean bg-ocean text-white"
                      : "border-slate-300 bg-white text-ocean"
                  }`}
                  onClick={() =>
                    setCandidateSkills((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, review_status: "approved" } : item,
                      ),
                    )
                  }
                  type="button"
                  aria-label="Approve skill"
                >
                  <Check size={16} aria-hidden="true" />
                  Correct
                </button>
                <button
                  className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-medium ${
                    skill.review_status === "rejected"
                      ? "border-red-700 bg-red-700 text-white"
                      : "border-slate-300 bg-white text-red-700"
                  }`}
                  onClick={() =>
                    setCandidateSkills((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, review_status: "rejected" } : item,
                      ),
                    )
                  }
                  type="button"
                  aria-label="Reject skill"
                >
                  <X size={16} aria-hidden="true" />
                  Wrong
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}

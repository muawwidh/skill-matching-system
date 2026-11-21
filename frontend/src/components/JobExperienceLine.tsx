import { BriefcaseBusiness } from "lucide-react";

import type { RecommendationItem } from "../types/documents";

/** The job's ESCO occupation and, when available, the candidate's related experience (D060). Never affects order. */
export function JobExperienceLine({ item }: { item: RecommendationItem }) {
  const occupation = item.job_occupation;
  const related = item.related_experience;
  if (!occupation) return null;
  return (
    <div className="mt-3 space-y-1">
    {related ? (
      <p
        className={`text-sm ${related.meets_requirement ? "text-emerald-800" : "text-amber-900"}`}
        title="From your work entries whose ESCO occupation is in the same ISCO group as this job. Overlapping periods are counted once. This never changes the order of jobs."
      >
        About {related.relevant_years} year{related.relevant_years === 1 ? "" : "s"} in related roles (ISCO {related.isco_group}{" "}
        {related.isco_group_label}) · job asks {related.min_required_years}+ years →{" "}
        <span className="font-medium">{related.meets_requirement ? "meets requirement" : "below requirement"}</span>
      </p>
    ) : null}
    <div className="flex flex-wrap items-start gap-2 text-xs text-slate-600">
      <BriefcaseBusiness size={14} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
      <span title="ESCO occupation linked automatically from the job title">
        {occupation.determined
          ? `ESCO occupation: ${occupation.label}${occupation.isco_code ? ` (ISCO ${occupation.isco_code} ${occupation.isco_unit_group})` : ""}`
          : "Occupation not determined"}
      </span>
    </div>
    </div>
  );
}

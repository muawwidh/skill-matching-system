import { BriefcaseBusiness } from "lucide-react";

import type { RecommendationItem } from "../types/documents";

/** The job's ESCO occupation and, when available, the candidate's related experience (D060). Never affects order. */
export function JobExperienceLine({ item }: { item: RecommendationItem }) {
  const occupation = item.job_occupation;
  if (!occupation) return null;
  return (
    <div className="mt-3 flex flex-wrap items-start gap-2 text-xs text-slate-600">
      <BriefcaseBusiness size={14} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
      <span title="ESCO occupation linked automatically from the job title">
        {occupation.determined
          ? `ESCO occupation: ${occupation.label}${occupation.isco_code ? ` (ISCO ${occupation.isco_code} ${occupation.isco_unit_group})` : ""}`
          : "Occupation not determined"}
      </span>
    </div>
  );
}

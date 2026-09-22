import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

import type { CandidateJobMatch } from "../types/documents";

type JobMatchPanelProps = {
  match?: CandidateJobMatch;
  isRefreshing: boolean;
  onRefresh: () => void;
};

function SkillPills({ items, tone }: { items: string[]; tone: "good" | "gap" }) {
  if (items.length === 0) {
    return <span className="text-sm text-slate-500">None</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          className={`rounded px-2 py-1 text-xs ${
            tone === "good" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"
          }`}
          key={item}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export function JobMatchPanel({ match, isRefreshing, onRefresh }: JobMatchPanelProps) {
  const score = match ? Math.round(match.score) : 0;
  return (
    <section className="mt-4 rounded-md border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-ocean text-sm font-semibold text-white">
            {score}%
          </div>
          <div>
            <h3 className="text-sm font-semibold text-ink">Candidate Match</h3>
            <p className="text-xs text-slate-500">
              {match ? match.explanation : "Refresh after adding CV and job skills."}
            </p>
          </div>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700"
          disabled={isRefreshing}
          onClick={onRefresh}
          type="button"
        >
          <RefreshCw size={16} className={isRefreshing ? "animate-spin" : ""} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {match ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-emerald-800">
              <CheckCircle2 size={16} aria-hidden="true" />
              Matched skills
            </div>
            <SkillPills
              items={[...match.matched_required, ...match.matched_preferred]}
              tone="good"
            />
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-red-800">
              <AlertTriangle size={16} aria-hidden="true" />
              Skill gaps
            </div>
            <SkillPills
              items={[...match.missing_required, ...match.missing_preferred]}
              tone="gap"
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

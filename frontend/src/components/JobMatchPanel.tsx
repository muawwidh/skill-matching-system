import { AlertTriangle, CheckCircle2, ListChecks, RefreshCw } from "lucide-react";

import type { CandidateJobMatch, MatchedSkill } from "../types/documents";

type JobMatchPanelProps = {
  match?: CandidateJobMatch;
  isRefreshing: boolean;
  onRefresh: () => void;
  /** 1-based position in the backend ranking; undefined when the job has no coverage row. */
  rank?: number;
  rankTotal: number;
};

const MATCHED_VIA_LABEL: Record<MatchedSkill["matched_via"], string> = {
  taxonomy_concept: "Matched via taxonomy concept",
  skill_name: "Matched by same skill name",
};

function MatchedChips({ items }: { items: MatchedSkill[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-slate-500">None</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          className="cursor-help rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-800"
          key={item.label}
          title={MATCHED_VIA_LABEL[item.matched_via]}
        >
          {item.label}
        </span>
      ))}
    </div>
  );
}

function MissingChips({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-slate-500">None</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span className="rounded bg-red-50 px-2 py-1 text-xs text-red-800" key={item}>
          {item}
        </span>
      ))}
    </div>
  );
}

function CoverageCount({ label, matched, missing }: { label: string; matched: number; missing: number }) {
  const total = matched + missing;
  return (
    <p className="text-sm text-ink">
      <span className="font-medium">{label}:</span>{" "}
      {total === 0 ? "none listed that can be compared" : `${matched} of ${total} matched`}
    </p>
  );
}

export function JobMatchPanel({ match, isRefreshing, onRefresh, rank, rankTotal }: JobMatchPanelProps) {
  return (
    <section className="mt-4 rounded-md border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ListChecks size={20} className="text-ocean" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-ink">Skill coverage</h3>
          {rank !== undefined ? (
            <span
              className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
              title="Order: required coverage, then preferred coverage, then retrieval similarity, then job ID"
            >
              #{rank} of {rankTotal}
            </span>
          ) : null}
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
        <>
          <div className="mt-3 space-y-1">
            <CoverageCount
              label="Required skills"
              matched={match.matched_required.length}
              missing={match.missing_required.length}
            />
            <CoverageCount
              label="Preferred skills"
              matched={match.matched_preferred.length}
              missing={match.missing_preferred.length}
            />
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-emerald-800">
                <CheckCircle2 size={16} aria-hidden="true" />
                Covered skills
              </div>
              <MatchedChips items={[...match.matched_required, ...match.matched_preferred]} />
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-red-800">
                <AlertTriangle size={16} aria-hidden="true" />
                Missing skills
              </div>
              <MissingChips items={[...match.missing_required, ...match.missing_preferred]} />
            </div>
          </div>
          <p className="mt-3 whitespace-pre-line text-xs text-slate-600">{match.explanation}</p>
        </>
      ) : (
        <p className="mt-2 text-xs text-slate-500">Approve CV and job skills, then refresh to see skill coverage.</p>
      )}
    </section>
  );
}

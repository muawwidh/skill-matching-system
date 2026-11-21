import { AlertTriangle, CheckCircle2, CircleDashed, ListChecks } from "lucide-react";

import type { MatchedSkill, MissingSkill, PartialSkill, RecommendationItem } from "../types/documents";

type JobMatchPanelProps = {
  match: RecommendationItem;
  /** Number of retrieved jobs: "#rank of rankTotal". */
  rankTotal: number;
};

const UNREVIEWED = "automatically extracted, not reviewed";
const unreviewedClass = (item: { reviewed?: boolean }) => (item.reviewed === false ? " border border-dashed border-slate-400" : "");
const unreviewedNote = (item: { reviewed?: boolean }) => (item.reviewed === false ? ` · ${UNREVIEWED}` : "");

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
          className={`cursor-help rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-800${unreviewedClass(item)}`}
          key={item.label}
          title={MATCHED_VIA_LABEL[item.matched_via] + unreviewedNote(item)}
        >
          {item.label}
        </span>
      ))}
    </div>
  );
}

const CHECKED_VIA_LABEL: Record<MissingSkill["checked_via"], string> = {
  taxonomy_concept: "Not found in your CV by taxonomy concept or name",
  skill_name: "Not found in your CV by name (may appear under a different wording)",
};

function MissingChips({ items }: { items: MissingSkill[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-slate-500">None</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          className={`cursor-help rounded bg-red-50 px-2 py-1 text-xs text-red-800${unreviewedClass(item)}`}
          key={item.label}
          title={CHECKED_VIA_LABEL[item.checked_via] + unreviewedNote(item)}
        >
          {item.label}
        </span>
      ))}
    </div>
  );
}

function PartialChips({ items }: { items: PartialSkill[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          className={`cursor-help rounded bg-amber-50 px-2 py-1 text-xs text-amber-900${unreviewedClass(item)}`}
          key={item.label}
          title={`Not in your CV, but related: you have ${item.candidate_skill} (same ESCO area: ${item.broader_concept})${unreviewedNote(item)}`}
        >
          {item.label}
        </span>
      ))}
    </div>
  );
}

function CoverageCount({ label, matched, partial, missing }: { label: string; matched: number; partial: number; missing: number }) {
  const total = matched + partial + missing;
  return (
    <p className="text-sm text-ink">
      <span className="font-medium">{label}:</span>{" "}
      {total === 0 ? "none listed" : `${matched} of ${total} matched`}
      {partial > 0 ? ` (${partial} related skill${partial === 1 ? "" : "s"} in your profile, not counted as matched)` : ""}
    </p>
  );
}

export function JobMatchPanel({ match, rankTotal }: JobMatchPanelProps) {
  const partial = [...match.partial_required, ...match.partial_preferred];
  const hasUnreviewed = [
    ...match.matched_required, ...match.matched_preferred, ...partial, ...match.missing_required, ...match.missing_preferred,
  ].some((item) => item.reviewed === false);
  return (
    <section className="mt-4 rounded-md border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <ListChecks size={20} className="text-ocean" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-ink">Skill coverage</h3>
        <span
          className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
          title="Position among the jobs retrieved for your profile by semantic similarity. Skill coverage below explains the job; it does not change the order."
        >
          #{match.rank} of {rankTotal}
        </span>
      </div>
      <div className="mt-3 space-y-1">
        <CoverageCount label="Required skills" matched={match.matched_required.length} partial={match.partial_required.length} missing={match.missing_required.length} />
        <CoverageCount label="Preferred skills" matched={match.matched_preferred.length} partial={match.partial_preferred.length} missing={match.missing_preferred.length} />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-emerald-800">
            <CheckCircle2 size={16} aria-hidden="true" />
            Covered skills
          </div>
          <MatchedChips items={[...match.matched_required, ...match.matched_preferred]} />
        </div>
        {partial.length > 0 ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 md:col-span-2">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-900">
              <CircleDashed size={16} aria-hidden="true" />
              Related skill in your profile
            </div>
            <PartialChips items={partial} />
          </div>
        ) : null}
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-red-800">
            <AlertTriangle size={16} aria-hidden="true" />
            Missing skills
          </div>
          <MissingChips items={[...match.missing_required, ...match.missing_preferred]} />
        </div>
      </div>
      {hasUnreviewed ? (
        <p className="mt-3 text-xs text-slate-600">
          Skills with a dashed outline were {UNREVIEWED}: they come from the job posting text and may be incomplete or wrong.
        </p>
      ) : null}
      <p className="mt-3 whitespace-pre-line text-xs text-slate-600">{match.explanation}</p>
    </section>
  );
}

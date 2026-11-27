import { coverageSegments, type CoverageCounts, type CoverageView } from "../utils/coverage";

type Segment = "matched" | "related" | "preview" | "missing";
const COLOR: Record<Segment, string> = {
  matched: "bg-have",
  related: "bg-related-bg ring-1 ring-inset ring-related/60",
  preview: "bg-gap animate-glow",
  missing: "bg-gap-bg ring-1 ring-inset ring-gap/45",
};

/**
 * Segmented coverage bar: one segment per counted skill (have, related, gap). With `closes`, the
 * "what if" preview adds solid orange segments for gaps the previewed skill would close. Never a percentage.
 */
export function SkillBar({ counts, closes = 0, label, className = "" }: {
  counts: CoverageCounts; closes?: number; label: string; className?: string;
}) {
  const base = coverageSegments(counts) as Segment[];
  const segments: Segment[] = [
    ...base.filter((s) => s === "matched"), ...base.filter((s) => s === "related"),
    ...Array<Segment>(closes).fill("preview"), ...base.filter((s) => s === "missing"),
  ];
  if (!segments.length) return <div aria-label={label} className={`h-2 rounded-full bg-mist ${className}`} role="img" />;
  return (
    <div aria-label={label} className={`flex origin-left animate-fill gap-[3px] ${className}`} role="img">
      {segments.map((segment, index) => (
        <span key={index} className={`h-2 flex-1 rounded-[3px] transition-colors duration-300 ${COLOR[segment]}`} />
      ))}
    </div>
  );
}

/** Bar with its text label (used where a sentence fits: detail panel, dashboard). */
export function CoverageBar({ counts, compact = false, view }: { counts?: CoverageCounts; compact?: boolean; view?: CoverageView }) {
  const shown = view?.counts ?? counts ?? { matched: 0, related: 0, missing: 0 };
  const label = view?.label ?? "";
  return (
    <div className={compact ? "space-y-1" : "space-y-1.5"}>
      <SkillBar counts={shown} label={view?.basis === "mentioned" || !view ? label : `Required skills: ${label}`} />
      {label ? <p className="text-xs text-muted">{label}</p> : null}
    </div>
  );
}

export function CoverageLegend() {
  const item = (color: string, text: string) => (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-4 rounded-[3px] ${color}`} aria-hidden="true" />
      {text}
    </span>
  );
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {item("bg-have", "have")}
      {item("bg-related-bg ring-1 ring-inset ring-related/60", "related")}
      {item("bg-gap-bg ring-1 ring-inset ring-gap/45", "gap")}
    </p>
  );
}

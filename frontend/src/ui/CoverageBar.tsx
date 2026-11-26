import { coverageLabel, coverageSegments, type CoverageCounts, type CoverageView } from "../utils/coverage";

const COLOR = { matched: "bg-teal", related: "bg-caution-bar", missing: "bg-neutral-bar" } as const;

/** One segment per skill (matched, related, missing) with a text label. Never a percentage. */
export function CoverageBar({ counts, compact = false, view }: { counts?: CoverageCounts; compact?: boolean; view?: CoverageView }) {
  const shown = view?.counts ?? counts ?? { matched: 0, related: 0, missing: 0 };
  const segments = coverageSegments(shown);
  const label = view?.label ?? coverageLabel(shown);
  return (
    <div className={compact ? "space-y-1" : "space-y-1.5"}>
      {segments.length > 0 ? (
        <div role="img" aria-label={view?.basis === "mentioned" ? label : `Required skills: ${label}`} className="flex gap-1">
          {segments.map((segment, index) => (
            <span key={index} className={`h-2 flex-1 rounded-sm ${COLOR[segment]}`} />
          ))}
        </div>
      ) : null}
      <p className="text-xs text-muted">{label}</p>
      {view?.note ? <p className="text-xs italic text-muted">{view.note}</p> : null}
    </div>
  );
}

export function CoverageLegend() {
  const item = (color: string, text: string) => (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-4 rounded-sm ${color}`} aria-hidden="true" />
      {text}
    </span>
  );
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {item("bg-teal", "matched")}
      {item("bg-caution-bar", "related skill in your profile")}
      {item("bg-neutral-bar", "missing")}
    </p>
  );
}

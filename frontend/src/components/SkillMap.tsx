import { X } from "lucide-react";

import { riseDelay } from "../ui/Page";
import { groupByArea, statusCounts, type MapNode, type MapStatus } from "../utils/skillMap";

const NODE: Record<MapStatus, string> = {
  have: "border-have/30 bg-have-bg text-have-text",
  related: "border-dashed border-related bg-related-bg text-related-text",
  gap: "border-gap/40 bg-gap-bg text-gap-text",
  idle: "border-idle bg-white text-idle-text",
};
const DOT: Record<MapStatus, string> = {
  have: "bg-have", related: "border border-dashed border-related bg-related-bg", gap: "bg-gap", idle: "border border-idle bg-white",
};
export const STATUS_WORD: Record<MapStatus, string> = { have: "have", related: "related", gap: "gap", idle: "not needed" };

export type LegendEntry = { status: MapStatus; label: string };
const JOB_LEGEND: LegendEntry[] = (["have", "related", "gap", "idle"] as MapStatus[]).map((status) => ({ status, label: STATUS_WORD[status] }));

/**
 * Skills grouped by ESCO area; colour = status for the selected job (or the profile). Nodes are
 * focusable and carry their status and comparison detail as text (not colour only).
 */
export function SkillMap({ nodes, glow, legend = JOB_LEGEND, onRemove, label = "Skill map" }: {
  nodes: MapNode[]; glow?: string | null; legend?: LegendEntry[]; onRemove?: (node: MapNode) => void; label?: string;
}) {
  const groups = groupByArea(nodes);
  const counts = statusCounts(nodes);
  const glowKey = glow?.trim().toLowerCase();
  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
        {legend.map(({ status, label: text }) => (
          <li key={status} className="inline-flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${DOT[status]}`} aria-hidden="true" />
            {text} <span className="numeral text-ink">{counts[status]}</span>
          </li>
        ))}
        {nodes.some((node) => node.required) ? <li className="font-semibold text-ink">bold = required</li> : null}
      </ul>
      <div className="grid gap-2.5 sm:grid-cols-2" role="list" aria-label={label}>
        {groups.map((group, index) => (
          <section key={group.key} role="listitem" className="animate-rise rounded-xl border border-line bg-white p-3" style={riseDelay(index)}
            aria-label={`${group.name}: ${group.nodes.length} skill${group.nodes.length === 1 ? "" : "s"}`}>
            <h4 className="eyebrow mb-2 flex justify-between gap-2"><span>{group.name}</span><span className="numeral">{group.nodes.length}</span></h4>
            <ul className="flex flex-wrap gap-1.5">
              {group.nodes.map((node) => {
                const glowing = glowKey && node.label.trim().toLowerCase() === glowKey;
                return (
                  <li
                    key={node.id ?? node.label}
                    className={`inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${NODE[node.status]} ${node.required ? "font-semibold" : "font-medium"} ${glowing ? "animate-glow ring-2 ring-gap" : ""}`}
                    tabIndex={0}
                    title={node.detail ? `${node.detail}${node.unreviewed ? " · automatic, not reviewed" : ""}` : undefined}
                  >
                    <span className="truncate">{node.label}</span>
                    <span className="sr-only">
                      {`, ${STATUS_WORD[node.status]}${node.required ? ", required" : ""}${node.detail ? `. ${node.detail}` : ""}`}
                    </span>
                    {node.removable && onRemove ? (
                      <button aria-label={`Remove ${node.label}`} className="-mr-1 grid h-5 w-5 place-items-center rounded-full hover:bg-black/10"
                        onClick={() => onRemove(node)} type="button">
                        <X size={12} aria-hidden="true" />
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

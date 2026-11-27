/**
 * Skill map and "what if I learned" helpers (pure, unit-tested). Display only: nothing here
 * changes the order of jobs; the preview recomputes coverage counts from data already loaded.
 */
import { coverageView, type CoverageCounts } from "./coverage.ts";

export type EscoAreaLike = { code: string; label: string } | null | undefined;
export type MapStatus = "have" | "related" | "gap" | "idle";
export type MapNode = {
  label: string;
  status: MapStatus;
  required?: boolean;
  /** Tooltip text: how the skill was compared. */
  detail?: string;
  area?: EscoAreaLike;
  unreviewed?: boolean;
  /** Profile map: a skill added by hand can be removed. */
  removable?: boolean;
  id?: string;
};
export type AreaGroup = { key: string; name: string; nodes: MapNode[] };

export const OTHER_AREA = "Other";

/** Short names for the ESCO groups one level below the top (skills S1–S8, transversal T1–T6, knowledge 00–10, L1). */
const AREA_NAMES: Record<string, string> = {
  S1: "Communication & creativity", S2: "Information skills", S3: "Assisting & caring", S4: "Management",
  S5: "Working with computers", S6: "Handling & moving", S7: "Constructing", S8: "Machinery & equipment",
  T1: "Core skills", T2: "Thinking", T3: "Self-management", T4: "Social & communication", T5: "Physical & manual",
  T6: "Life skills", L1: "Languages",
  "00": "Generic programmes", "01": "Education", "02": "Arts & humanities", "03": "Social sciences & journalism",
  "04": "Business, admin & law", "05": "Sciences & maths", "06": "ICT", "07": "Engineering & construction",
  "08": "Agriculture & veterinary", "09": "Health & welfare", "10": "Services",
};

export function areaName(area: EscoAreaLike): string {
  if (!area) return OTHER_AREA;
  const short = AREA_NAMES[area.code];
  if (short) return short;
  const label = area.label.replace(/\s*\([^)]*\)\s*$/, "").trim();
  return label ? label[0].toUpperCase() + label.slice(1) : OTHER_AREA;
}

const STATUS_ORDER: Record<MapStatus, number> = { have: 0, related: 1, gap: 2, idle: 3 };
const fold = (label: string) => label.trim().toLowerCase();

/**
 * Group nodes by ESCO area. Areas with more of the job's skills come first; "Other" (no ESCO area) last.
 * Within an area: have, related, gap, not needed; then by label. One node per label (first wins).
 */
export function groupByArea(nodes: MapNode[]): AreaGroup[] {
  const seen = new Set<string>();
  const groups = new Map<string, AreaGroup>();
  for (const node of nodes) {
    if (seen.has(fold(node.label))) continue;
    seen.add(fold(node.label));
    const name = areaName(node.area);
    const key = node.area ? node.area.code || name : OTHER_AREA;
    const group = groups.get(key) ?? { key, name, nodes: [] };
    group.nodes.push(node);
    groups.set(key, group);
  }
  const weight = (group: AreaGroup) => group.nodes.filter((node) => node.status !== "idle").length;
  for (const group of groups.values()) {
    group.nodes.sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
      || Number(Boolean(b.required)) - Number(Boolean(a.required)) || a.label.localeCompare(b.label));
  }
  return [...groups.values()].sort((a, b) =>
    Number(a.key === OTHER_AREA) - Number(b.key === OTHER_AREA) || weight(b) - weight(a)
    || b.nodes.length - a.nodes.length || a.name.localeCompare(b.name));
}

type Entry = { label: string; reviewed?: boolean; esco_area?: EscoAreaLike };
type JobInput = {
  matched_required: (Entry & { matched_via: string })[];
  matched_preferred: (Entry & { matched_via: string })[];
  partial_required: (Entry & { candidate_skill: string; broader_concept: string })[];
  partial_preferred: (Entry & { candidate_skill: string; broader_concept: string })[];
  missing_required: (Entry & { checked_via: string })[];
  missing_preferred: (Entry & { checked_via: string })[];
  not_needed?: Entry[];
};

const MATCHED_VIA: Record<string, string> = { taxonomy_concept: "same ESCO concept", skill_name: "same name" };
const CHECKED_VIA: Record<string, string> = {
  taxonomy_concept: "not found by ESCO concept or name",
  skill_name: "not found by name; may be in your CV in other words",
};

/** The selected job's skills (have / related / gap) plus the candidate's skills it does not ask for (idle). */
export function jobMapNodes(item: JobInput): MapNode[] {
  const node = (entry: Entry, status: MapStatus, required: boolean, detail: string): MapNode => ({
    label: entry.label, status, required, detail, area: entry.esco_area, unreviewed: entry.reviewed === false,
  });
  const tag = (required: boolean) => (required ? "Required" : "Mentioned");
  return [
    ...item.matched_required.map((e) => node(e, "have", true, `${tag(true)} · you have it (${MATCHED_VIA[e.matched_via] ?? e.matched_via})`)),
    ...item.matched_preferred.map((e) => node(e, "have", false, `${tag(false)} · you have it (${MATCHED_VIA[e.matched_via] ?? e.matched_via})`)),
    ...item.partial_required.map((e) => node(e, "related", true, `${tag(true)} · related: you have ${e.candidate_skill} (${e.broader_concept})`)),
    ...item.partial_preferred.map((e) => node(e, "related", false, `${tag(false)} · related: you have ${e.candidate_skill} (${e.broader_concept})`)),
    ...item.missing_required.map((e) => node(e, "gap", true, `${tag(true)} · gap: ${CHECKED_VIA[e.checked_via] ?? e.checked_via}`)),
    ...item.missing_preferred.map((e) => node(e, "gap", false, `${tag(false)} · gap: ${CHECKED_VIA[e.checked_via] ?? e.checked_via}`)),
    ...(item.not_needed ?? []).map((e) => node(e, "idle", false, "In your profile · not asked for by this job")),
  ];
}

export function statusCounts(nodes: MapNode[]): Record<MapStatus, number> {
  const counts: Record<MapStatus, number> = { have: 0, related: 0, gap: 0, idle: 0 };
  for (const node of nodes) counts[node.status] += 1;
  return counts;
}

// --- What if I learned ---------------------------------------------------------------------------

type CoverageInput = Parameters<typeof coverageView>[0];

/** Gap labels the coverage bar counts for one job (required gaps, or mentioned ones when none is required). */
export function barGaps(item: CoverageInput): string[] {
  return coverageView(item).chips.filter((chip) => chip.kind === "missing").map((chip) => chip.label);
}

/** The most frequent bar gaps across the given jobs: each counted once per job; ties by label. */
export function topGaps(items: CoverageInput[], limit = 5): { label: string; count: number }[] {
  const counts = new Map<string, { label: string; count: number }>();
  for (const item of items) {
    for (const label of new Set(barGaps(item).map(fold))) {
      const original = barGaps(item).find((gap) => fold(gap) === label) as string;
      const entry = counts.get(label) ?? { label: original, count: 0 };
      entry.count += 1;
      counts.set(label, entry);
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)).slice(0, limit);
}

export type Preview = { counts: CoverageCounts; closes: number };

/** Coverage counts if the candidate had `skill`: a matching gap moves to "closes" (shown as an orange segment). */
export function previewCoverage(item: CoverageInput, skill: string | null): Preview {
  const counts = coverageView(item).counts;
  if (!skill) return { counts, closes: 0 };
  const closes = barGaps(item).filter((gap) => fold(gap) === fold(skill)).length;
  return { counts: { ...counts, missing: counts.missing - closes }, closes };
}

/** "+Docker → closes a gap in 3 of 10 matches". */
export function whatIfSummary(skill: string, items: CoverageInput[]): string {
  const closing = items.filter((item) => previewCoverage(item, skill).closes > 0).length;
  return `+${skill} → closes a gap in ${closing} of ${items.length} match${items.length === 1 ? "" : "es"}`;
}

/** "3/5" for the card: matched of all counted skills; "—" when the job lists none. */
export function fraction(counts: CoverageCounts, extra = 0): string {
  const total = counts.matched + counts.related + counts.missing + extra;
  return total ? `${counts.matched + extra}/${total}` : "—";
}

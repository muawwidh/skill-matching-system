import { experienceBadge } from "../utils/coverage";

export function RankBadge({ rank, large = false }: { rank: number; large?: boolean }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-lg bg-night font-display font-semibold text-white ${large ? "h-11 min-w-11 px-2 text-base" : "h-8 min-w-8 px-1.5 text-sm"}`}
      title="Position among the jobs found for your profile, closest in meaning first"
    >
      #{rank}
    </span>
  );
}

const TONE = {
  meets: "bg-teal-soft text-teal-text",
  below: "border border-dashed border-caution-line bg-caution-bg text-caution-text",
  neutral: "bg-neutral-bg text-neutral-text",
} as const;

export function ExperienceBadge({ item }: { item: Parameters<typeof experienceBadge>[0] }) {
  const badge = experienceBadge(item);
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${TONE[badge.tone]}`} title={badge.title}>
      {badge.text}
    </span>
  );
}

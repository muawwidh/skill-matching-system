import { experienceBadge } from "../utils/coverage";

/** Big rank numeral ("01"); the position in the retrieval order. */
export function RankBadge({ rank, large = false }: { rank: number; large?: boolean }) {
  return (
    <span className={`numeral shrink-0 leading-none text-[#B3BAC4] ${large ? "text-5xl" : "w-12 text-4xl"}`} aria-label={`Rank ${rank}`}>
      {String(rank).padStart(2, "0")}
    </span>
  );
}

const TONE = {
  meets: "border border-have/25 bg-have-bg text-have-text",
  below: "border border-gap/30 bg-gap-bg text-gap-text",
  neutral: "border border-line bg-mist text-idle-text",
} as const;

export function ExperienceBadge({ item }: { item: Parameters<typeof experienceBadge>[0] }) {
  const badge = experienceBadge(item);
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${TONE[badge.tone]}`} title={badge.title}>
      {badge.text}
    </span>
  );
}

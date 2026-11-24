/** Pure helpers for the coverage bar and the experience badge (no React, unit-tested). */

export type CoverageCounts = { matched: number; related: number; missing: number };
export type Segment = "matched" | "related" | "missing";

type ItemCounts = {
  matched_required: unknown[];
  partial_required?: unknown[];
  missing_required: unknown[];
};

export function requiredCounts(item: ItemCounts): CoverageCounts {
  return {
    matched: item.matched_required.length,
    related: item.partial_required?.length ?? 0,
    missing: item.missing_required.length,
  };
}

/** One segment per required skill: matched first, then related, then missing. */
export function coverageSegments({ matched, related, missing }: CoverageCounts): Segment[] {
  return [
    ...Array<Segment>(matched).fill("matched"),
    ...Array<Segment>(related).fill("related"),
    ...Array<Segment>(missing).fill("missing"),
  ];
}

/** "X of Y required skills · N related"; never a percentage. */
export function coverageLabel({ matched, related, missing }: CoverageCounts): string {
  const total = matched + related + missing;
  if (total === 0) return "No required skills listed";
  return `${matched} of ${total} required skills${related > 0 ? ` · ${related} related` : ""}`;
}

type LanguageInput = { compared: boolean; matched: unknown[]; missing: unknown[] };

/** "Languages: X of Y matched", or null when the job's languages were not compared. Separate from skill counts. */
export function languageLabel(languages: LanguageInput | undefined | null): string | null {
  if (!languages?.compared) return null;
  const total = languages.matched.length + languages.missing.length;
  return total ? `Languages: ${languages.matched.length} of ${total} matched` : null;
}

export type ExperienceBadge = { tone: "meets" | "below" | "neutral"; text: string; title: string };

type ExperienceInput = {
  related_experience?: { meets_requirement: boolean; min_required_years: number; relevant_years: number } | null;
  min_required_years?: number | null;
};

export function experienceBadge(item: ExperienceInput): ExperienceBadge {
  const related = item.related_experience;
  if (related) {
    const years = `about ${related.relevant_years} year${related.relevant_years === 1 ? "" : "s"} in related roles`;
    return related.meets_requirement
      ? { tone: "meets", text: `Meets ${related.min_required_years}+ years`, title: `You have ${years}.` }
      : { tone: "below", text: `Below ${related.min_required_years}+ years`, title: `You have ${years}.` };
  }
  if (item.min_required_years != null) {
    return {
      tone: "neutral",
      text: `Asks ${item.min_required_years}+ years`,
      title: "Not compared: add work entries with an occupation, or the job's occupation could not be determined.",
    };
  }
  return { tone: "neutral", text: "No experience stated", title: "The posting states no minimum years of experience." };
}

/** "posted 3 days ago" style text; null when unknown. */
export function postedAgo(iso: string | null | undefined, now: Date = new Date()): string | null {
  if (!iso) return null;
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
  if (Number.isNaN(days)) return null;
  if (days <= 0) return "posted today";
  if (days === 1) return "posted yesterday";
  if (days < 30) return `posted ${days} days ago`;
  const months = Math.floor(days / 30);
  return months < 12 ? `posted ${months} month${months === 1 ? "" : "s"} ago` : "posted over a year ago";
}

/** Page numbers to show around the current page, with null for a gap. */
export function pageList(page: number, pages: number): (number | null)[] {
  const wanted = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const sorted = [...wanted].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  sorted.forEach((n, i) => {
    if (i > 0 && n - sorted[i - 1] > 1) out.push(null);
    out.push(n);
  });
  return out;
}

/** Initials for the avatar button: first letters of the first two words, else of the e-mail. */
export function initials(fullName: string | undefined, email: string | undefined): string {
  const words = (fullName ?? "").trim().split(/\s+/).filter(Boolean);
  const letters = words.length ? words.slice(0, 2).map((w) => w[0]) : [(email ?? "?")[0]];
  return letters.join("").toUpperCase();
}

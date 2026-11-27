import type { CandidateSkillGroup, EscoArea, ManualSkill } from "../types/documents";

export type SkillKind = "confirmed" | "review" | "added";
/** `manualIds`: the hand-added skills behind this entry (removable). */
export type ProfileSkill = {
  key: string; label: string; kind: SkillKind; linked: boolean; cvIds: string[]; manualIds: string[];
  /** ESCO area for the profile's skill map (display only). */
  area?: EscoArea | null;
};
export type SkillSummary = { skills: ProfileSkill[]; confirmed: number; linked: number; review: number };

type CandidateSkill = ManualSkill;
const isManual = (item: CandidateSkill) => item.source === "manual_review";

/**
 * One entry per distinct skill across all CVs and the skills added by hand.
 * confirmed: approved CV skill; added: approved skill added by hand; review: only pending occurrences.
 * Rejected skills are left out. `linked`: the skill has a selected ESCO link.
 */
export function summarizeSkills(groupsByCv: { cvId: string; groups: CandidateSkillGroup[] }[], manual: CandidateSkill[]): SkillSummary {
  const byKey = new Map<string, { label: string; linked: boolean; occurrences: CandidateSkill[]; cvIds: Set<string>; area?: EscoArea | null }>();
  for (const { cvId, groups } of groupsByCv) {
    // Languages have their own card on My profile.
    for (const group of groups.filter((g) => !g.occurrences.every((item) => item.skill_type === "language"))) {
      const key = group.label.trim().toLowerCase();
      const entry = byKey.get(key) ?? { label: group.label, linked: false, occurrences: [], cvIds: new Set<string>() };
      entry.linked ||= Boolean(group.taxonomy);
      entry.area ??= group.esco_area ?? null;
      for (const item of group.occurrences) {
        if (!entry.occurrences.some((known) => known.id === item.id)) entry.occurrences.push(item);
      }
      if (group.occurrences.some((item) => !isManual(item))) entry.cvIds.add(cvId);
      byKey.set(key, entry);
    }
  }
  for (const item of manual.filter((skill) => skill.skill_type !== "language")) {
    const key = item.raw_text.trim().toLowerCase();
    const entry = byKey.get(key) ?? { label: item.raw_text, linked: false, occurrences: [], cvIds: new Set<string>() };
    if (!entry.occurrences.some((known) => known.id === item.id)) entry.occurrences.push(item);
    entry.area ??= item.esco_area ?? null;
    byKey.set(key, entry);
  }
  const skills: ProfileSkill[] = [];
  for (const [key, entry] of byKey) {
    const approved = entry.occurrences.filter((item) => item.review_status === "approved");
    let kind: SkillKind | null = null;
    if (approved.some((item) => !isManual(item))) kind = "confirmed";
    else if (approved.length > 0) kind = "added";
    else if (entry.occurrences.some((item) => item.review_status === "pending")) kind = "review";
    const manualIds = entry.occurrences.filter(isManual).map((item) => item.id);
    if (kind) skills.push({ key, label: entry.label, kind, linked: entry.linked, cvIds: [...entry.cvIds], manualIds, area: entry.area ?? null });
  }
  skills.sort((a, b) => a.label.localeCompare(b.label));
  const counted = skills.filter((skill) => skill.kind !== "review");
  return {
    skills,
    confirmed: counted.length,
    linked: counted.filter((skill) => skill.linked).length,
    review: skills.length - counted.length,
  };
}

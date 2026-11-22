import { useQueries, useQuery } from "@tanstack/react-query";

import { listCvSkillGroups, listCvs, listManualSkills } from "../api/documents";
import { summarizeSkills } from "../utils/skills";

/** CVs, their skill groups and the skills added by hand, merged into one summary (candidate accounts). */
export function useSkillSummary(accessToken: string, enabled = true) {
  const cvs = useQuery({ queryKey: ["cvs"], queryFn: () => listCvs(accessToken), enabled });
  const manual = useQuery({ queryKey: ["manual-skills"], queryFn: () => listManualSkills(accessToken), enabled });
  const groups = useQueries({
    queries: (cvs.data ?? []).map((cv) => ({
      queryKey: ["cv", cv.id, "skills", "groups"],
      queryFn: () => listCvSkillGroups(accessToken, cv.id),
      enabled,
    })),
  });
  const loading = cvs.isLoading || manual.isLoading || groups.some((query) => query.isLoading);
  const summary = loading
    ? null
    : summarizeSkills(
        (cvs.data ?? []).map((cv, index) => ({ cvId: cv.id, groups: groups[index]?.data ?? [] })),
        manual.data ?? [],
      );
  return { cvs, manual, summary, loading, error: cvs.error ?? manual.error ?? groups.find((query) => query.error)?.error ?? null };
}

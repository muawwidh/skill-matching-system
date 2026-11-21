import { useQuery } from "@tanstack/react-query";
import { Info, UserCheck } from "lucide-react";

import { getMatchingProfile } from "../api/documents";
import type { SkillStatusCounts } from "../types/documents";

function counts(value: SkillStatusCounts) {
  return `${value.approved} approved · ${value.pending} pending · ${value.rejected} rejected`;
}

/** Which CVs and manually added skills feed matching (D041). Only approved skills are used. */
export function MatchingProfileBox({ accessToken }: { accessToken: string }) {
  const query = useQuery({
    queryKey: ["matching-profile"],
    queryFn: () => getMatchingProfile(accessToken),
  });
  const profile = query.data;
  const unattributed = profile ? profile.unattributed_skills.approved + profile.unattributed_skills.pending + profile.unattributed_skills.rejected : 0;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5" aria-labelledby="matching-profile-heading">
      <div className="flex items-center gap-2">
        <UserCheck size={20} className="text-ocean" aria-hidden="true" />
        <h2 id="matching-profile-heading" className="text-lg font-semibold text-ink">Your matching profile</h2>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Job matching combines all of your CVs below and the skills you added by hand. Only skills you approved are used.
      </p>
      {query.isLoading ? <p className="mt-3 text-sm text-slate-500">Loading...</p> : null}
      {query.error ? <p role="alert" className="mt-3 text-sm text-red-700">{query.error.message}</p> : null}
      {profile ? (
        <>
          <ul className="mt-3 divide-y divide-slate-100 text-sm">
            {profile.cvs.map((cv) => (
              <li key={cv.id} className="flex flex-wrap justify-between gap-2 py-2">
                <span className="font-medium text-ink">{cv.original_filename}</span>
                <span className="text-slate-600">{counts(cv.skills)}</span>
              </li>
            ))}
            <li className="flex flex-wrap justify-between gap-2 py-2">
              <span className="font-medium text-ink">Skills added by hand</span>
              <span className="text-slate-600">{counts(profile.manual_skills)}</span>
            </li>
            {unattributed > 0 ? (
              <li className="flex flex-wrap justify-between gap-2 py-2">
                <span className="font-medium text-ink">Earlier extracted skills without a CV</span>
                <span className="text-slate-600">{counts(profile.unattributed_skills)}</span>
              </li>
            ) : null}
          </ul>
          {profile.cvs.length === 0 ? <p className="mt-2 text-sm text-slate-500">No CVs yet.</p> : null}
          {profile.retrieval_status !== "ready" ? (
            <p role="status" className="mt-3 flex gap-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
              <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              {profile.retrieval_message}
            </p>
          ) : (
            <p className="mt-3 text-sm text-emerald-800">Your matching profile is up to date.</p>
          )}
        </>
      ) : null}
    </section>
  );
}

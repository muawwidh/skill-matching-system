import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Save, X } from "lucide-react";
import { useState } from "react";

import { listCvSkillGroups, reviewCvSkills } from "../api/documents";
import type { CandidateSkill } from "../types/documents";

export function CandidateSkillGroups({ accessToken, cvId }: { accessToken: string; cvId: string }) {
  const cache = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, Partial<CandidateSkill>>>({});
  const [saved, setSaved] = useState(false);
  const query = useQuery({
    queryKey: ["cv", cvId, "skills", "groups"],
    queryFn: () => listCvSkillGroups(accessToken, cvId),
    refetchOnWindowFocus: "always",
    refetchInterval: 30000,
  });
  const save = useMutation({
    mutationFn: () => reviewCvSkills(accessToken, cvId,
      (query.data ?? []).flatMap((group) => group.occurrences.map((item) => ({ ...item, ...drafts[item.id] })))),
    onSuccess: async () => {
      setDrafts({});
      setSaved(true);
      await cache.invalidateQueries({ queryKey: ["cv", cvId, "skills"] });
      await cache.invalidateQueries({ queryKey: ["taxonomy"] });
    },
  });
  function edit(id: string, patch: Partial<CandidateSkill>) {
    setSaved(false);
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch } }));
  }
  if (query.isLoading) return <p className="text-sm text-slate-500">Loading skills...</p>;
  return <section className="mt-4 border-t border-slate-200 pt-4">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-sm font-semibold">Skills and indicators</h3>
      <button type="button" disabled={save.isPending || query.isFetching || !Object.keys(drafts).length}
        onClick={() => save.mutate()} className="inline-flex items-center gap-2 rounded bg-ocean px-3 py-2 text-sm text-white disabled:opacity-50">
        <Save size={16} />{save.isPending ? "Saving..." : "Save review"}
      </button>
    </div>
    {query.error || save.error ? <p role="alert" className="text-sm text-red-700">{(query.error ?? save.error)?.message}</p> : null}
    {saved ? <p role="status" className="mb-2 text-sm text-ocean">Review saved.</p> : null}
    {Object.keys(drafts).length ? <p role="status" className="mb-2 text-sm text-amber-800">Unsaved review changes</p> : null}
    {!query.data?.length && !query.error ? <p className="text-sm text-slate-500">No skills or indicators extracted yet.</p> : null}
    <div className="divide-y divide-slate-200">{query.data?.map((group) => {
      const occurrences = group.occurrences.map((item) => ({ ...item, ...drafts[item.id] }));
      const changedText = group.occurrences.some((item) => drafts[item.id]?.raw_text !== undefined && drafts[item.id].raw_text !== item.raw_text);
      const counts = occurrences.reduce<Record<string, number>>((result, item) => {
        result[item.review_status] = (result[item.review_status] ?? 0) + 1; return result;
      }, {});
      return <details key={group.key} className="py-3">
        <summary className="cursor-pointer break-words text-sm">
          <span className="font-semibold">{changedText ? "Unsaved skill correction" : group.label}</span>
          <span className="ml-2 text-slate-500">{occurrences.length} occurrence{occurrences.length === 1 ? "" : "s"}</span>
          <span className="mt-1 block text-xs text-slate-600">{changedText ? "Taxonomy link will be cleared for corrected occurrences" : group.taxonomy
            ? `Taxonomy-linked: ${group.taxonomy.source} ${group.taxonomy.version} · ${group.taxonomy.external_id}`
            : `Unlinked · ${occurrences[0].skill_type.replace(/_/g, " ")}`}</span>
          <span className="mt-1 block text-xs text-slate-600">
            {Object.keys(counts).length > 1 ? "Mixed extraction review · " : "Extraction review · "}
            {Object.entries(counts).map(([status, count]) => `${count} ${status}`).join(" · ")}
            {` · ${counts.approved ?? 0} confirmed support`}
          </span>
        </summary>
        <ul className="mt-3 divide-y divide-slate-100">{occurrences.map((item) => <li key={item.id} className="py-3">
          <div className="flex flex-wrap items-center gap-2">
            <input aria-label={`Skill occurrence ${item.id}`} value={item.raw_text} disabled={save.isPending}
              className="w-full min-w-0 rounded border border-slate-300 px-2 py-1 text-sm sm:w-64"
              onChange={(event) => edit(item.id, { raw_text: event.target.value, normalized_text: event.target.value.toLowerCase() })} />
            <span className="text-xs text-slate-500">{item.skill_type} · {Math.round(item.confidence_score * 100)}% extraction confidence · {item.review_status}</span>
          </div>
          <p className="my-2 whitespace-pre-wrap break-words text-sm text-slate-600">{item.evidence_sentence || "No evidence text"}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-label={`Approve occurrence ${item.id}`} disabled={save.isPending}
              aria-pressed={item.review_status === "approved"} onClick={() => edit(item.id, { review_status: "approved" })}
              className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-sm text-ocean"><Check size={16} />Correct</button>
            <button type="button" aria-label={`Reject occurrence ${item.id}`} disabled={save.isPending}
              aria-pressed={item.review_status === "rejected"} onClick={() => edit(item.id, { review_status: "rejected" })}
              className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-sm text-red-700"><X size={16} />Wrong</button>
          </div>
        </li>)}</ul>
      </details>;
    })}</div>
  </section>;
}

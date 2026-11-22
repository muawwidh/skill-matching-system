import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, X } from "lucide-react";

import { listMyCvTaxonomyLinks, reviewMyCvTaxonomyLink } from "../api/taxonomy";
import type { TaxonomyLinkCandidate, TaxonomyReviewGroup } from "../types/taxonomy";
import { matchMethodLabel } from "./TaxonomyReviewPanel";
import { LoadingBlock } from "../ui/Feedback";

type Action = { group: TaxonomyReviewGroup; candidate: TaxonomyLinkCandidate; status: "approved" | "rejected" };

const button = "inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-sm disabled:opacity-50";

/**
 * Lets a candidate confirm or reject the taxonomy concepts suggested for the skills in their own CV (D048).
 * Uncertain suggestions are never applied automatically; staff can still review them too.
 */
export function CandidateTaxonomyLinks({ accessToken, cvId }: { accessToken: string; cvId: string }) {
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: ["cv", cvId, "taxonomy-links"],
    queryFn: () => listMyCvTaxonomyLinks(accessToken, cvId),
  });
  const review = useMutation({
    mutationFn: ({ group, candidate, status }: Action) => {
      const switching = status === "approved" && group.selection && group.selection.candidate_id !== candidate.id;
      return reviewMyCvTaxonomyLink(accessToken, cvId, candidate.id, status, switching ? group.selection?.token : undefined);
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["cv", cvId] });
      await cache.invalidateQueries({ queryKey: ["matching-profile"] });
      await cache.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const groups = query.data ?? [];
  if (query.isLoading) return <div className="mt-4"><LoadingBlock label="Loading ESCO suggestions" lines={2} /></div>;
  if (!groups.length && !query.error) return null;

  return (
    <section className="mt-4 border-t border-line pt-4" aria-labelledby={`links-${cvId}`}>
      <div className="flex items-center gap-2">
        <Link2 size={16} className="text-ocean" aria-hidden="true" />
        <h3 id={`links-${cvId}`} className="text-sm font-semibold">Taxonomy links for your skills</h3>
      </div>
      <p className="mt-1 text-xs text-muted">
        A link to an ESCO or O*NET concept lets your skill match a job skill worded differently. Confirm the concept
        that means your skill, or mark suggestions as wrong.
      </p>
      {query.error || review.error ? (
        <p role="alert" className="mt-2 text-sm text-miss-text">{(query.error ?? review.error)?.message}</p>
      ) : null}
      <ul className="mt-2 divide-y divide-line">
        {groups.map((group) => (
          <li key={group.extracted_term_id} className="py-3 text-sm">
            <p>
              <span className="font-semibold">{group.raw_text}</span>
              <span className="ml-2 text-muted">
                {group.selection ? `linked to ${group.selection.concept.preferred_label}` : "not linked"}
              </span>
            </p>
            <ul className="mt-2 space-y-2">
              {group.candidates.map((candidate) => {
                const selected = group.selection?.candidate_id === candidate.id;
                return (
                  <li key={candidate.id} className="flex flex-wrap items-center gap-2">
                    <span className={selected ? "font-medium text-teal-text" : "text-ink"}>
                      {candidate.concept.preferred_label}
                    </span>
                    <span className="text-xs text-muted">
                      {candidate.concept.source_code} {candidate.concept.taxonomy_version} · {matchMethodLabel(candidate.match_method)} · {candidate.review_status}
                    </span>
                    {!selected ? (
                      <button
                        className={`${button} text-ocean`}
                        disabled={review.isPending}
                        onClick={() => review.mutate({ group, candidate, status: "approved" })}
                        type="button"
                        aria-label={`Use ${candidate.concept.preferred_label} for ${group.raw_text}`}
                      >
                        <Check size={14} aria-hidden="true" />
                        {group.selection ? "Use this instead" : "Use this"}
                      </button>
                    ) : null}
                    {candidate.review_status !== "rejected" ? (
                      <button
                        className={`${button} text-miss-text`}
                        disabled={review.isPending}
                        onClick={() => review.mutate({ group, candidate, status: "rejected" })}
                        type="button"
                        aria-label={`${candidate.concept.preferred_label} is wrong for ${group.raw_text}`}
                      >
                        <X size={14} aria-hidden="true" />
                        {selected ? "Remove link" : "Wrong"}
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}

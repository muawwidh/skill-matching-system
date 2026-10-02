import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ArrowRightLeft, Check, History, Search, X } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { listTaxonomyReviewHistory, listTaxonomyReviews, reviewTaxonomyLink } from "../api/taxonomy";
import type { TaxonomyLinkCandidate, TaxonomyReviewGroup } from "../types/taxonomy";

type Action = { group: TaxonomyReviewGroup; candidate: TaxonomyLinkCandidate; status: "approved" | "rejected" };
const button = "inline-flex items-center gap-1 rounded border border-slate-300 px-3 py-2 text-sm disabled:opacity-50";

function ReviewHistory({ accessToken, group }: { accessToken: string; group: TaxonomyReviewGroup }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const history = useQuery({
    queryKey: ["taxonomy", "history", group.term_source, group.extracted_term_id, offset],
    queryFn: () => listTaxonomyReviewHistory(accessToken, group.term_source, group.extracted_term_id, offset),
    enabled: open,
  });
  return <details className="mt-3 text-sm" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-slate-600"><History className="mr-1 inline" size={14} />Review history</summary>
    {history.isLoading ? <p className="py-2">Loading history...</p> : null}
    {history.error ? <p role="alert" className="py-2 text-red-700">{history.error.message}</p> : null}
    {history.data?.length === 0 ? <p className="py-2 text-slate-500">No recorded review events on this page.</p> : null}
    <ol className="divide-y divide-slate-200">{history.data?.map((event) => <li className="py-3" key={event.id}>
      <p className="font-medium">{event.action}: {event.after_state.candidates.find((item) => item.id === event.candidate_id)?.label}</p>
      <p>{event.before_state.selection?.label ?? "No selection"} &rarr; {event.after_state.selection?.label ?? "No selection"}</p>
      {event.after_state.candidates.filter((item) => event.before_state.candidates.find((old) => old.id === item.id)?.status !== item.status)
        .map((item) => <p className="text-slate-600" key={item.id}>{item.label}: {item.status}</p>)}
      <p className="mt-1 break-all text-xs text-slate-500">{new Date(event.created_at).toLocaleString()} · Reviewer {event.reviewer_id ?? "Deleted account"}</p>
    </li>)}</ol>
    {(offset > 0 || history.data?.length === 20) ? <div className="flex gap-2 py-2">
      <button className={button} disabled={!offset || history.isFetching} onClick={() => setOffset(Math.max(0, offset - 20))} type="button"><ArrowLeft size={14} />Earlier page</button>
      <button className={button} disabled={history.data?.length !== 20 || history.isFetching} onClick={() => setOffset(offset + 20)} type="button">Older events<ArrowRight size={14} /></button>
    </div> : null}
  </details>;
}

function Confirmation({ action, busy, onCancel, onConfirm }: { action: Action; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  const replace = action.status === "approved";
  return <dialog ref={ref} aria-labelledby="review-confirm-title" onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
    className="w-[calc(100%_-_2rem)] max-w-lg rounded-md border border-slate-300 p-6 backdrop:bg-black/40">
    <h3 id="review-confirm-title" className="text-lg font-semibold">{replace ? "Replace taxonomy selection?" : "Reject current selection?"}</h3>
    <p className="mt-3 break-words">{action.group.raw_text}: <strong>{action.group.selection?.concept.preferred_label}</strong></p>
    <p className="mt-2 break-words">{replace ? <>New selection: <strong>{action.candidate.concept.preferred_label}</strong>. The previous selection becomes superseded, not rejected.</> : "The selected taxonomy link will be removed."}</p>
    <div className="mt-5 flex flex-wrap justify-end gap-2">
      <button autoFocus className={button} disabled={busy} onClick={onCancel} type="button">Cancel</button>
      <button className={`${button} bg-ocean text-white`} disabled={busy} onClick={onConfirm} type="button">
        {replace ? <ArrowRightLeft size={16} /> : <X size={16} />}{busy ? "Saving..." : replace ? "Confirm replacement" : "Reject and remove link"}
      </button>
    </div>
  </dialog>;
}

export function TaxonomyReviewPanel({ accessToken }: { accessToken: string }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState("pending");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [confirmation, setConfirmation] = useState<Action | null>(null);
  const [notice, setNotice] = useState("");
  const reviews = useQuery({
    queryKey: ["taxonomy", "reviews", state, filter, offset],
    queryFn: () => listTaxonomyReviews(accessToken, state, filter, offset),
  });
  const mutation = useMutation({
    mutationFn: (action: Action) => reviewTaxonomyLink(accessToken, action.candidate.id, action.status,
      action.status === "approved" && Boolean(action.group.selection && action.group.selection.candidate_id !== action.candidate.id),
      action.group.selection?.token ?? null),
    onSuccess: (_, action) => {
      setConfirmation(null);
      setNotice(action.status === "approved" ? `Selected ${action.candidate.concept.preferred_label} for ${action.group.raw_text}.` : `Rejected ${action.candidate.concept.preferred_label} for ${action.group.raw_text}.`);
      queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
      queryClient.invalidateQueries({ queryKey: ["cv"] });
    },
    onError: () => { setConfirmation(null); queryClient.invalidateQueries({ queryKey: ["taxonomy"] }); },
  });
  function review(action: Action) {
    setNotice("");
    mutation.reset();
    const changingSelection = action.group.selection && (action.status === "approved"
      ? action.group.selection.candidate_id !== action.candidate.id
      : action.group.selection.candidate_id === action.candidate.id);
    if (changingSelection) setConfirmation(action);
    else mutation.mutate(action);
  }
  function search(event: FormEvent) { event.preventDefault(); setFilter(query.trim()); setOffset(0); }
  return <section className="border-t border-slate-200 pt-6">
    <h2 className="text-lg font-semibold text-ink">Taxonomy review</h2>
    <div role="tablist" aria-label="Review status" className="mt-3 flex gap-5 border-b border-slate-200">
      {[["pending", "Pending"], ["selected", "Selected"], ["all", "All"]].map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={state === value}
        className={`border-b-2 px-1 py-2 text-sm ${state === value ? "border-ocean font-semibold text-ocean" : "border-transparent text-slate-600"}`}
        onClick={() => { setState(value); setOffset(0); }}>{label}</button>)}
    </div>
    <form className="mt-4 flex max-w-xl gap-2" onSubmit={search}>
      <input aria-label="Find review term" placeholder="Term or extracted term ID" className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" value={query} onChange={(event) => setQuery(event.target.value)} />
      <button className={button} aria-label="Find review" title="Find review" type="submit"><Search size={16} /></button>
    </form>
    {notice ? <p role="status" className="mt-3 text-sm text-ocean">{notice}</p> : null}
    {mutation.error || reviews.error ? <p role="alert" className="mt-3 text-sm text-red-700">{(mutation.error ?? reviews.error)?.message}</p> : null}
    {reviews.isLoading ? <p className="py-4 text-sm">Loading reviews...</p> : null}
    {reviews.data?.items.length === 0 ? <p className="py-4 text-sm text-slate-500">No reviews in this view.</p> : null}
    <div className="mt-4 space-y-4">{reviews.data?.items.map((group) => <article className="min-w-0 rounded-md border border-slate-200 bg-white p-4" key={`${group.term_source}:${group.extracted_term_id}`}>
      <h3 className="break-words font-semibold">{group.raw_text}</h3>
      <p className="mt-1 break-all text-xs text-slate-500">{group.term_source} · {group.extracted_term_id}</p>
      <p className="my-3 break-words text-sm"><span className="font-medium">Current selection: </span>{group.selection?.concept.preferred_label ?? "None"}</p>
      {group.inconsistent ? <p role="alert" className="mb-3 text-sm text-amber-800">Stored review statuses conflict with the current link. Selection confirmation or replacement will reconcile this term.</p> : null}
      <ul className="divide-y divide-slate-200 border-y border-slate-200">{group.candidates.map((item) => {
        const selected = group.selection?.candidate_id === item.id;
        return <li className="flex flex-wrap items-center justify-between gap-3 py-3" key={item.id}>
          <div className="min-w-0 flex-1 basis-56 break-words">
            <p className="text-sm font-medium">{item.rank}. {item.concept.preferred_label}</p>
            <p className="mt-1 text-xs text-slate-500">{item.concept.source_code} {item.concept.taxonomy_version} · {item.match_method.replace(/_/g, " ")} · {Math.round(item.confidence_score * 100)}%</p>
            <p className={`mt-1 text-xs ${selected ? "font-semibold text-ocean" : "text-slate-600"}`} title={item.review_status === "superseded" ? "Previously selected; not marked incorrect" : undefined}>
              {selected ? "Selected" : item.review_status === "approved" ? "Inconsistent: not selected" : item.review_status === "superseded" ? "Superseded (previous selection)" : item.review_status}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className={`${button} text-ocean`} disabled={mutation.isPending || Boolean(selected && !group.inconsistent)} type="button" onClick={() => review({ group, candidate: item, status: "approved" })}>
              {group.selection && !selected ? <ArrowRightLeft size={15} /> : <Check size={15} />}{selected ? group.inconsistent ? "Confirm selection" : "Selected" : group.selection ? "Replace selection" : "Select"}
            </button>
            <button className={`${button} text-red-700`} disabled={mutation.isPending || (item.review_status === "rejected" && !selected)} type="button" onClick={() => review({ group, candidate: item, status: "rejected" })}><X size={15} />{selected ? "Reject selection" : "Reject"}</button>
          </div>
        </li>;
      })}</ul>
      <ReviewHistory accessToken={accessToken} group={group} />
    </article>)}</div>
    <div className="mt-4 flex items-center justify-between gap-2">
      <button className={button} disabled={offset === 0 || reviews.isFetching} onClick={() => setOffset(Math.max(0, offset - 20))} type="button"><ArrowLeft size={16} />Previous</button>
      <span className="text-sm text-slate-500">Page {offset / 20 + 1}</span>
      <button className={button} disabled={!reviews.data?.has_more || reviews.isFetching} onClick={() => setOffset(offset + 20)} type="button">Next<ArrowRight size={16} /></button>
    </div>
    {confirmation ? <Confirmation action={confirmation} busy={mutation.isPending} onCancel={() => setConfirmation(null)} onConfirm={() => mutation.mutate(confirmation)} /> : null}
  </section>;
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, X } from "lucide-react";
import { useState } from "react";

import { addLanguage, listLanguages, removeLanguage, reviewLanguage } from "../api/documents";
import { LANGUAGE_LEVELS, type ProfileLanguage } from "../types/documents";
import { Chip } from "../ui/Chip";
import { ErrorText, LoadingBlock } from "../ui/Feedback";
import { CardTitle } from "../ui/Page";

const QUERIES = [["languages"], ["cv"], ["recommendations"]];

/**
 * Languages on My profile: found in a CV (to confirm) or added by hand with an optional level.
 * Compared by name with a job's language requirements; never part of the ranking or the skill counts.
 */
export function LanguagesPanel({ accessToken }: { accessToken: string }) {
  const queryClient = useQueryClient();
  const languages = useQuery({ queryKey: ["languages"], queryFn: () => listLanguages(accessToken) });
  const refresh = () => { for (const key of QUERIES) queryClient.invalidateQueries({ queryKey: key }); };
  const review = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approved" | "rejected" }) => reviewLanguage(accessToken, id, decision),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (id: string) => removeLanguage(accessToken, id), onSuccess: refresh });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [level, setLevel] = useState("");
  const add = useMutation({
    mutationFn: () => addLanguage(accessToken, name, level || null),
    onSuccess: () => { setName(""); setLevel(""); setOpen(false); refresh(); },
  });

  const all = languages.data ?? [];
  const pending = all.filter((entry) => entry.status === "pending");
  const confirmed = all.filter((entry) => entry.status === "approved");
  const label = (entry: ProfileLanguage) => (entry.level ? `${entry.label} · ${entry.level}` : entry.label);

  return (
    <section className="card space-y-4" aria-labelledby="languages-heading">
      <CardTitle id="languages-heading">Languages</CardTitle>
      <p className="text-sm text-muted">
        Compared by name with the languages a job asks for (“in your profile” / “not found in your profile”).
        Levels are shown only to you and are not compared. Languages never change the order of your jobs.
      </p>
      {languages.isLoading ? <LoadingBlock label="Loading languages" /> : null}
      <ErrorText error={languages.error ?? review.error ?? remove.error} />
      {confirmed.length ? (
        <div className="flex flex-wrap gap-1.5">
          {confirmed.map((entry) => (
            <Chip key={entry.id} kind="teal"
              title={entry.origin === "cv" ? `Found in your CV: “${entry.evidence}”` : entry.origin === "added" ? "Added by you" : "Added in the skill editor"}
              onRemove={entry.origin === "added" ? () => remove.mutate(entry.id) : entry.origin === "cv" ? () => review.mutate({ id: entry.id, decision: "rejected" }) : undefined}
              removeLabel={`Remove ${entry.label}`}>
              {label(entry)}
            </Chip>
          ))}
        </div>
      ) : languages.data ? <p className="text-sm text-muted">No confirmed languages yet.</p> : null}
      {pending.length ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-ink">Found in your CV — please confirm</p>
          <ul className="divide-y divide-line">
            {pending.map((entry) => (
              <li key={entry.id} className="flex items-center gap-2 py-2 text-sm">
                <span className="flex-1">
                  <span className="font-medium text-ink">{entry.label}</span>
                  {entry.evidence ? <span className="block truncate text-xs text-muted">“{entry.evidence}”</span> : null}
                </span>
                <button aria-label={`Confirm ${entry.label}`} className="btn-secondary" disabled={review.isPending}
                  onClick={() => review.mutate({ id: entry.id, decision: "approved" })} type="button">
                  <Check size={14} aria-hidden="true" /> Confirm
                </button>
                <button aria-label={`Reject ${entry.label}`} className="btn-secondary" disabled={review.isPending}
                  onClick={() => review.mutate({ id: entry.id, decision: "rejected" })} type="button">
                  <X size={14} aria-hidden="true" /> Reject
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {open ? (
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (name.trim()) add.mutate(); }}>
          <label className="text-sm text-ink">
            Language
            <input autoFocus className="field mt-1 block w-44" maxLength={60} onChange={(event) => setName(event.target.value)} placeholder="e.g. German" value={name} />
          </label>
          <label className="text-sm text-ink">
            Level (optional)
            <select className="field mt-1 block w-32" onChange={(event) => setLevel(event.target.value)} value={level}>
              <option value="">—</option>
              {LANGUAGE_LEVELS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <button className="btn-primary" disabled={!name.trim() || add.isPending} type="submit">Add</button>
          <button className="btn-secondary" onClick={() => setOpen(false)} type="button">Cancel</button>
          <div className="w-full"><ErrorText error={add.error} /></div>
        </form>
      ) : (
        <button className="btn-secondary" onClick={() => setOpen(true)} type="button">
          <Plus size={16} aria-hidden="true" /> Add a language
        </button>
      )}
    </section>
  );
}

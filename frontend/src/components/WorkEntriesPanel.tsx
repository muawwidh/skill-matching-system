import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { createWorkEntry, deleteWorkEntry, listDetectedWorkEntries, listWorkEntries, updateWorkEntry } from "../api/experience";
import type { DetectedWorkEntry, WorkEntry, WorkEntryPayload } from "../types/experience";
import { Chip } from "../ui/Chip";
import { LoadingBlock } from "../ui/Feedback";
import { OccupationPicker, type OccupationChoice } from "./OccupationPicker";

type Draft = WorkEntryPayload & {
  id: string | null;
  present: boolean;
  /** undefined until the candidate chooses (or a strong match is preselected); null: "None of these". */
  occupation: OccupationChoice;
  occupationPreselected: boolean;
  titleChoices?: string[];
};

const emptyDraft: Draft = {
  id: null,
  title: "",
  start_month: "",
  end_month: null,
  present: false,
  occupation_concept_id: null,
  occupation: undefined,
  occupationPreselected: false,
  source: "manual",
};

const monthLabel = (value: string | null) =>
  value ? new Date(`${value}-01T00:00:00`).toLocaleDateString(undefined, { month: "short", year: "numeric" }) : "present";

const durationLabel = (months: number) => {
  const years = Math.floor(months / 12);
  const rest = months % 12;
  return [years ? `${years} yr${years === 1 ? "" : "s"}` : "", rest ? `${rest} mo` : ""].filter(Boolean).join(" ") || "0 mo";
};

/**
 * Self-entered work history for "relevant experience". Candidate accounts only.
 * No employer is asked for or stored. Entries detected in a CV only pre-fill the form.
 */
export function WorkEntriesPanel({ accessToken, cvNames = {} }: { accessToken: string; cvNames?: Record<string, string> }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [missingOccupation, setMissingOccupation] = useState(false);
  const entries = useQuery({ queryKey: ["work-entries"], queryFn: () => listWorkEntries(accessToken) });
  const detected = useQuery({ queryKey: ["work-entries", "detected"], queryFn: () => listDetectedWorkEntries(accessToken) });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["work-entries"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
  }

  const save = useMutation({
    mutationFn: (value: Draft) => {
      const payload: WorkEntryPayload = {
        title: value.title,
        start_month: value.start_month,
        end_month: value.present ? null : value.end_month,
        occupation_concept_id: value.occupation_concept_id,
        source: value.source,
        source_cv_id: value.source === "cv_detected" ? value.source_cv_id ?? null : null,
      };
      return value.id ? updateWorkEntry(accessToken, value.id, payload) : createWorkEntry(accessToken, payload);
    },
    onSuccess: () => {
      setDraft(null);
      setMissingOccupation(false);
      refresh();
    },
  });
  const remove = useMutation({ mutationFn: (id: string) => deleteWorkEntry(accessToken, id), onSuccess: refresh });

  function edit(entry: WorkEntry) {
    setDraft({
      id: entry.id,
      title: entry.title,
      start_month: entry.start_month,
      end_month: entry.end_month,
      present: entry.end_month === null,
      occupation_concept_id: entry.occupation?.concept_id ?? null,
      occupation: entry.occupation,
      occupationPreselected: false,
      source: entry.source,
      source_cv_id: entry.source_cv_id,
    });
  }

  function useDetected(item: DetectedWorkEntry) {
    setMissingOccupation(false);
    setDraft({ ...emptyDraft, title: item.title, start_month: item.start_month, end_month: item.end_month,
      present: item.end_month === null, source: "cv_detected", source_cv_id: item.cv_id, titleChoices: item.title ? [] : item.title_choices ?? [] });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    if (draft.occupation === undefined) {
      setMissingOccupation(true);
      return;
    }
    save.mutate(draft);
  }

  const field = "field";
  const sorted = [...(entries.data ?? [])].sort((a, b) => b.start_month.localeCompare(a.start_month));
  return (
    <section className="card scroll-mt-4" id="experience" aria-labelledby="work-entries-heading">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <h2 id="work-entries-heading" className="text-lg font-semibold text-ink">Work experience</h2>
        {!draft ? (
          <button className="btn-secondary" onClick={() => { setMissingOccupation(false); setDraft(emptyDraft); }} type="button">
            <Plus size={16} aria-hidden="true" /> Add experience
          </button>
        ) : null}
      </div>
      <p className="text-sm text-muted">
        Job title and dates only (no employer). Used to show your years of related experience for each job. It never changes
        the ranking; you can optionally hide jobs above your experience.
      </p>

      {draft ? (
        <form className="mt-4 space-y-3 rounded-xl border border-line bg-mist p-4" onSubmit={submit}>
          {draft.titleChoices && draft.titleChoices.length > 0 ? (
            <fieldset className="text-sm">
              <legend className="text-ink">Which of these is your job title?</legend>
              <div className="mt-1 flex flex-wrap gap-2">
                {draft.titleChoices.map((choice) => (
                  <button
                    key={choice}
                    aria-pressed={draft.title === choice}
                    className={`rounded-full border px-3 py-1 ${draft.title === choice ? "border-teal bg-teal-soft text-teal-text" : "border-line bg-white"}`}
                    onClick={() => setDraft({ ...draft, title: choice })}
                    type="button"
                  >
                    {choice}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted">Or type it below if none of these is right.</p>
            </fieldset>
          ) : null}
          <label className="block text-sm">
            <span className="text-ink">Job title</span>
            <input className={`mt-1 w-full ${field}`} maxLength={255} required value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="block text-ink">Start month</span>
              <input className={`mt-1 ${field}`} required type="month" value={draft.start_month}
                onChange={(event) => setDraft({ ...draft, start_month: event.target.value })} />
            </label>
            <label className="text-sm">
              <span className="block text-ink">End month</span>
              <input className={`mt-1 ${field}`} disabled={draft.present} required={!draft.present} type="month"
                value={draft.present ? "" : draft.end_month ?? ""}
                onChange={(event) => setDraft({ ...draft, end_month: event.target.value || null })} />
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink">
              <input checked={draft.present} className="accent-teal" type="checkbox" onChange={(event) => setDraft({ ...draft, present: event.target.checked })} />
              Present
            </label>
          </div>
          <OccupationPicker
            accessToken={accessToken}
            title={draft.title}
            value={draft.occupation}
            preselected={draft.occupationPreselected}
            missing={missingOccupation}
            onChange={(occupation, preselected) =>
              setDraft((current) => current && { ...current, occupation, occupationPreselected: preselected,
                occupation_concept_id: occupation?.concept_id ?? null })}
          />
          {save.error ? <p role="alert" className="text-sm text-miss-text">{save.error.message}</p> : null}
          <div className="flex gap-2">
            <button className="btn-primary" disabled={save.isPending} type="submit">
              {draft.id ? "Save changes" : "Add entry"}
            </button>
            <button className="btn-secondary" onClick={() => setDraft(null)} type="button">
              <X size={14} aria-hidden="true" /> Cancel
            </button>
          </div>
        </form>
      ) : null}

      {entries.isLoading ? <div className="mt-4"><LoadingBlock label="Loading work experience" /></div> : null}
      {sorted.length ? (
        <ol className="mt-5">
          {sorted.map((entry, index) => {
            const fromCv = entry.source_cv_id ? cvNames[entry.source_cv_id] : undefined;
            return (
              <li key={entry.id} className="relative flex gap-4 pb-5 last:pb-0">
                {index < sorted.length - 1 ? <span aria-hidden="true" className="absolute left-[7px] top-5 h-full w-0.5 bg-line" /> : null}
                <span aria-hidden="true" className={`relative mt-1.5 h-4 w-4 shrink-0 rounded-full border-2 ${entry.end_month === null ? "border-teal bg-teal" : "border-teal bg-white"}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-semibold text-ink">{entry.title}</p>
                      <p className="text-sm text-muted">
                        {monthLabel(entry.start_month)} – {monthLabel(entry.end_month)} · {durationLabel(entry.months)}
                        {fromCv ? ` · from ${fromCv}` : ""}
                      </p>
                    </div>
                    <div className="flex gap-1.5">
                      <button aria-label={`Edit ${entry.title}`} className="btn-secondary h-8 w-8 p-0" onClick={() => edit(entry)} type="button">
                        <Pencil size={14} aria-hidden="true" />
                      </button>
                      <button aria-label={`Delete ${entry.title}`} className="btn-danger h-8 w-8 p-0"
                        disabled={remove.isPending} onClick={() => remove.mutate(entry.id)} type="button">
                        <Trash2 size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-2">
                    {entry.occupation ? (
                      <Chip kind="teal" title={entry.occupation.isco_unit_group || undefined}>{entry.occupation.label}</Chip>
                    ) : (
                      <Chip kind="neutral">No occupation: not used for related experience</Chip>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
      {entries.data?.length === 0 && !draft ? (
        <p className="mt-4 text-sm text-muted">No work entries yet. Add one, or use the dates found in your CV below.</p>
      ) : null}

      {detected.data && detected.data.length > 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-caution-line bg-caution-bg p-4">
          <h3 className="text-sm font-semibold text-caution-text">Found in your CV</h3>
          <p className="text-xs text-caution-text">Check the title and months, then add them; nothing is saved until you do.</p>
          <ul className="mt-2 space-y-1.5">
            {detected.data.map((item) => (
              <li key={`${item.start_month}-${item.end_month}`} className="flex flex-wrap items-center justify-between gap-2 text-sm text-ink">
                <span>
                  {item.title || (item.title_choices?.length ? "Job title to choose" : "Untitled")} · {monthLabel(item.start_month)} – {monthLabel(item.end_month)}
                  {item.month_precision ? "" : " (year only: check the months)"}
                </span>
                <button className="btn-secondary px-3 py-1 text-xs" onClick={() => useDetected(item)} type="button">
                  Use
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

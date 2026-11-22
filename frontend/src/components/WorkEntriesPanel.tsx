import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BriefcaseBusiness, Pencil, Plus, Trash2, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { createWorkEntry, deleteWorkEntry, listDetectedWorkEntries, listWorkEntries, updateWorkEntry } from "../api/experience";
import type { DetectedWorkEntry, WorkEntry, WorkEntryPayload } from "../types/experience";
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
 * Self-entered work history for "relevant experience" (D060). Candidate accounts only.
 * No employer is asked for or stored. Entries detected in a CV only pre-fill the form.
 */
export function WorkEntriesPanel({ accessToken }: { accessToken: string }) {
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

  const field = "rounded-md border border-slate-300 px-3 py-2 text-sm";
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5" aria-labelledby="work-entries-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BriefcaseBusiness size={20} className="text-ocean" aria-hidden="true" />
          <h2 id="work-entries-heading" className="text-xl font-semibold text-ink">Work experience</h2>
        </div>
        {!draft ? (
          <button className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={() => { setMissingOccupation(false); setDraft(emptyDraft); }} type="button">
            <Plus size={16} aria-hidden="true" /> Add entry
          </button>
        ) : null}
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Job title and dates only (no employer). Used to show your years of related experience for each job. It never changes
        the ranking; you can optionally hide jobs above your experience.
      </p>

      {draft ? (
        <form className="mt-4 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3" onSubmit={submit}>
          {draft.titleChoices && draft.titleChoices.length > 0 ? (
            <fieldset className="text-sm">
              <legend className="text-slate-700">Which of these is your job title?</legend>
              <div className="mt-1 flex flex-wrap gap-2">
                {draft.titleChoices.map((choice) => (
                  <button
                    key={choice}
                    className={`rounded-md border px-2 py-1 ${draft.title === choice ? "border-ocean bg-ocean/10" : "border-slate-300"}`}
                    onClick={() => setDraft({ ...draft, title: choice })}
                    type="button"
                  >
                    {choice}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-slate-500">Or type it below if none of these is right.</p>
            </fieldset>
          ) : null}
          <label className="block text-sm">
            <span className="text-slate-700">Job title</span>
            <input className={`mt-1 w-full ${field}`} maxLength={255} required value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          </label>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="block text-slate-700">Start month</span>
              <input className={`mt-1 ${field}`} required type="month" value={draft.start_month}
                onChange={(event) => setDraft({ ...draft, start_month: event.target.value })} />
            </label>
            <label className="text-sm">
              <span className="block text-slate-700">End month</span>
              <input className={`mt-1 ${field}`} disabled={draft.present} required={!draft.present} type="month"
                value={draft.present ? "" : draft.end_month ?? ""}
                onChange={(event) => setDraft({ ...draft, end_month: event.target.value || null })} />
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
              <input checked={draft.present} type="checkbox" onChange={(event) => setDraft({ ...draft, present: event.target.checked })} />
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
          {save.error ? <p role="alert" className="text-sm text-red-700">{save.error.message}</p> : null}
          <div className="flex gap-2">
            <button className="rounded-md bg-ocean px-3 py-1.5 text-sm font-medium text-white" disabled={save.isPending} type="submit">
              {draft.id ? "Save changes" : "Add entry"}
            </button>
            <button className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={() => setDraft(null)} type="button">
              <X size={14} aria-hidden="true" /> Cancel
            </button>
          </div>
        </form>
      ) : null}

      <ul className="mt-4 divide-y divide-slate-100">
        {entries.data?.map((entry) => (
          <li key={entry.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
            <div>
              <p className="font-medium text-ink">{entry.title}</p>
              <p className="text-sm text-slate-600">
                {monthLabel(entry.start_month)} – {monthLabel(entry.end_month)} · {durationLabel(entry.months)}
              </p>
              <p className="text-xs text-slate-500">
                {entry.occupation
                  ? `ESCO occupation: ${entry.occupation.label}${entry.occupation.isco_code ? ` (ISCO ${entry.occupation.isco_code})` : ""}`
                  : "No occupation chosen: not used for related experience"}
              </p>
            </div>
            <div className="flex gap-2">
              <button aria-label={`Edit ${entry.title}`} className="grid h-8 w-8 place-items-center rounded-md border border-slate-300" onClick={() => edit(entry)} type="button">
                <Pencil size={14} aria-hidden="true" />
              </button>
              <button aria-label={`Delete ${entry.title}`} className="grid h-8 w-8 place-items-center rounded-md border border-slate-300 text-red-700"
                disabled={remove.isPending} onClick={() => remove.mutate(entry.id)} type="button">
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          </li>
        ))}
        {entries.data?.length === 0 ? <li className="py-3 text-sm text-slate-500">No work entries yet.</li> : null}
      </ul>

      {detected.data && detected.data.length > 0 ? (
        <div className="mt-4 rounded-md border border-dashed border-slate-300 p-3">
          <h3 className="text-sm font-semibold text-ink">Detected in your CV</h3>
          <p className="text-xs text-slate-500">Dates found in your CV. Check the title and months, then add them; nothing is saved until you do.</p>
          <ul className="mt-2 space-y-1">
            {detected.data.map((item) => (
              <li key={`${item.start_month}-${item.end_month}`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>
                  {item.title || (item.title_choices?.length ? "Job title to choose" : "Untitled")} · {monthLabel(item.start_month)} – {monthLabel(item.end_month)}
                  {item.month_precision ? "" : " (year only: check the months)"}
                </span>
                <button className="rounded-md border border-slate-300 px-2 py-1 text-xs" onClick={() => useDetected(item)} type="button">
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

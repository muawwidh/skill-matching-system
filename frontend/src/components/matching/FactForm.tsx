import { useState, type FormEvent } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { Fact, FactBody } from "../../types/matching";
import { Field, Options, reviews } from "./Controls";

export function FactForm({ facts, candidate, sourceIds = [], disabled, createDisabled = false, save, remove }: {
  facts: Fact[]; candidate: boolean; sourceIds?: string[]; disabled: boolean; createDisabled?: boolean;
  save: (fact: FactBody) => Promise<void>; remove: (id: string) => void;
}) {
  const [kind, setKind] = useState<FactBody["fact_type"]>("qualification");
  const [completion, setCompletion] = useState("unknown");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const text = (key: string) => String(data.get(key) ?? "").trim();
    await save({ fact_type: kind, statement: text("statement"), completion,
      duration_months: text("duration") === "" ? null : Number(text("duration")), field: text("field"), scope: text("scope"),
      evidence_reference: text("reference"), review_status: text("review") as FactBody["review_status"],
      cv_document_id: candidate ? text("cv") || null : null,
      taxonomy_concept_id: kind === "occupation" ? text("concept") || null : null,
      taxonomy_release_id: kind === "occupation" ? text("release") || null : null });
    form.reset(); setKind("qualification"); setCompletion("unknown");
  }
  return <section className="match-section">
    <h2>{candidate ? "Candidate-confirmed facts" : "Reviewed job facts"}</h2>
    <p className="match-muted">Preserve incomplete qualifications, duration and scope. Pending or rejected evidence does not contribute to alignment.</p>
    {facts.length === 0 && <p>No matching facts recorded.</p>}
    <ul className="divide-y divide-slate-200">{facts.map(fact => <li key={fact.id} className="py-3 flex gap-3 justify-between">
      <div className="min-w-0"><strong>{fact.statement}</strong><p>{fact.fact_type} · {fact.review_status} · {fact.completion}</p>
        <p>{fact.duration_months == null ? "Duration unknown" : `${fact.duration_months} months`} · {fact.field || "Field unspecified"} · {fact.scope || "Scope unspecified"}</p>
        <p className="match-muted">Evidence: {fact.evidence_reference}</p></div>
      <button className="match-icon" disabled={disabled} type="button" title="Delete fact" aria-label={`Delete fact: ${fact.statement}`} onClick={() => remove(fact.id)}><Trash2 size={18} aria-hidden="true" /></button>
    </li>)}</ul>
    <form onSubmit={event => { void submit(event).catch(() => undefined); }}>
      <fieldset disabled={disabled || createDisabled} className="match-form">
        <legend>Add {candidate ? "candidate-confirmed" : "reviewed job"} fact</legend>
        <Field label="Fact type"><Options values={["occupation", "qualification", "experience"]} value={kind} onChange={e => setKind(e.target.value as FactBody["fact_type"])} /></Field>
        <Field label="Review status"><Options name="review" values={reviews} defaultValue="pending" /></Field>
        <Field label="Statement"><textarea required name="statement" maxLength={1000} /></Field>
        <Field label="Completion"><Options values={["unknown", "completed", "in_progress", "not_completed", "not_applicable"]} value={completion} onChange={e => setCompletion(e.target.value)} /></Field>
        <Field label="Duration in months (blank = unknown)"><input name="duration" type="number" min="0" step="1" /></Field>
        <Field label="Field"><input name="field" maxLength={255} /></Field>
        <Field label="Scope"><input name="scope" maxLength={500} /></Field>
        <Field label="Evidence reference"><input required name="reference" maxLength={255} /></Field>
        {candidate && <Field label="Source CV (optional)"><select name="cv"><option value="">No CV reference</option>{sourceIds.map((id, i) => <option key={id} value={id}>Owned CV {i + 1}</option>)}</select></Field>}
        {kind === "occupation" && <>
          <Field label="Reviewed occupation concept UUID (optional pair)"><input name="concept" pattern="[0-9a-fA-F-]{36}" /></Field>
          <Field label="Taxonomy release UUID (optional pair)"><input name="release" pattern="[0-9a-fA-F-]{36}" /></Field>
        </>}
        <button type="submit" className="match-primary"><Plus size={16} aria-hidden="true" />Add fact</button>
      </fieldset>
    </form>
  </section>;
}

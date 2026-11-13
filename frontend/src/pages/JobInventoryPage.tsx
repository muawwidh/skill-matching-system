import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Check, Plus, Trash2 } from "lucide-react";
import { listJobs } from "../api/documents";
import { inputWriter, jobInputs } from "../api/matching";
import { FactForm } from "../components/matching/FactForm";
import { classifications, ErrorNotice, Field, Loading, Options, reviews } from "../components/matching/Controls";
import { useAuth } from "../features/auth/AuthProvider";
import type { Applicability, Classification, GroupBody, InventoryBody, JobInputs, Review } from "../types/matching";

type Writer = ReturnType<typeof inputWriter>;
export function JobInventoryPage() {
  const { accessToken, user } = useAuth();
  const { jobId } = useParams();
  const navigate = useNavigate();
  const allowed = user?.roles.some(r => r.name === "admin" || r.name === "researcher");
  const client = useQueryClient();
  const jobs = useQuery({ queryKey: ["inventory-jobs", user?.id], queryFn: () => listJobs(accessToken!), enabled: Boolean(allowed && accessToken), retry: false });
  const key = ["job-inventory", user?.id, jobId];
  const inputs = useQuery({ queryKey: key, queryFn: () => jobInputs(accessToken!, jobId!), enabled: Boolean(allowed && accessToken && jobId), retry: false });
  const action = useMutation({ mutationFn: (fn: (writer: Writer) => Promise<unknown>) => fn(inputWriter(accessToken!, "jobs", jobId!, inputs.data!.fingerprint)), retry: false,
    onSuccess: async () => { await client.invalidateQueries({ queryKey: key }); await client.invalidateQueries({ queryKey: ["matching-run"] }); } });
  if (!user) return <Loading />;
  if (!allowed) return <p role="alert">Administrator or researcher role required.</p>;
  const disabled = action.isPending || inputs.isFetching || Boolean(inputs.error) || Boolean(action.error);
  const save = async (fn: (writer: Writer) => Promise<unknown>) => { await action.mutateAsync(fn); };
  const remove = (kind: "facts" | "groups", id: string) => { if (window.confirm(`Delete this ${kind === "facts" ? "fact" : "group"}? Current results and sign-off may become invalid.`)) action.mutate(writer => writer.remove(kind, id)); };
  return <div className="matching-page"><h1>Job inventory review</h1>
    <p className="match-muted">Reviewed matching inputs are separate from extraction and taxonomy review. No pending rows alone does not establish a complete inventory.</p>
    <ErrorNotice error={action.error || inputs.error || jobs.error} />
    <Field label="Job"><select value={jobId || ""} disabled={action.isPending} onChange={event => { action.reset(); navigate(event.target.value ? `/job-inventories/${event.target.value}` : "/job-inventories"); }}><option value="">Select a job</option>{jobs.data?.map(job => <option key={job.id} value={job.id}>{job.title} · {job.company || "Company unspecified"}</option>)}</select></Field>
    {jobs.data?.find(job => job.id === jobId) && <details><summary>Job source evidence</summary><p className="whitespace-pre-wrap">{jobs.data.find(job => job.id === jobId)!.description}</p></details>}
    {(jobs.isLoading || inputs.isLoading) && <Loading />}
    {!jobId && <p>Select a job inventory.</p>}
    {jobs.data?.length === 0 && <p>No jobs available.</p>}
    {jobId && <button type="button" disabled={action.isPending} onClick={() => { void inputs.refetch(); action.reset(); }}>Reload current inputs</button>}
    {inputs.data && !inputs.error && <div key={`${jobId}:${inputs.data.fingerprint}`}>
      <p role="status">Inventory sign-off: {inputs.data.inventory_current ? "current" : "absent or invalidated"}</p>
      <FactForm candidate={false} facts={inputs.data.facts} disabled={disabled} save={body => save(w => w.fact(body))} remove={id => remove("facts", id)} />
      <section className="match-section"><h2>Occurrence classification review</h2>
        {inputs.data.skills.length === 0 && <p>No extracted occurrences. Review the source before signing completeness.</p>}
        {inputs.data.skills.map(skill => {
          const review = inputs.data!.occurrences.find(x => x.job_skill_id === skill.id);
          return <form key={skill.id} className="match-occurrence" onSubmit={event => {
            event.preventDefault(); const data = new FormData(event.currentTarget);
            void save(w => w.classify(skill.id, String(data.get("classification")) as Classification, String(data.get("review")) as Review, String(data.get("reason")).trim())).catch(() => undefined);
          }}><h3>{skill.raw_text} <small>({skill.skill_type}; extraction {skill.review_status}; legacy {skill.requirement_type})</small></h3>
            <blockquote>{skill.evidence_sentence || "No evidence sentence available"}</blockquote>
            <fieldset disabled={disabled} className="match-form">
              <Field label="Matching classification"><Options name="classification" values={classifications} defaultValue={review?.classification || skill.requirement_type} /></Field>
              <Field label="Classification review status"><Options name="review" values={reviews} defaultValue={review?.review_status || "pending"} /></Field>
              <Field label="Review reason"><input required maxLength={1000} name="reason" defaultValue={review?.reason || ""} /></Field>
              <button type="submit"><Check size={16} aria-hidden="true" />Save classification review</button>
            </fieldset>
          </form>;
        })}
      </section>
      <section className="match-section"><h2>Requirement groups</h2>
        <ul>{inputs.data.groups.map(group => <li key={group.id} className="match-occurrence">
          <strong>{group.component} · {group.operator} · {group.classification} · {group.review_status}{group.critical ? " · critical" : ""}</strong>
          <ul>{inputs.data!.members.filter(m => m.group_id === group.id).map(m => <li key={m.job_skill_id || m.job_matching_fact_id}>
            {m.job_skill_id ? inputs.data!.skills.find(x => x.id === m.job_skill_id)?.raw_text || "Unavailable occurrence" : inputs.data!.facts.find(x => x.id === m.job_matching_fact_id)?.statement || "Unavailable fact"}</li>)}</ul>
          <button type="button" disabled={disabled} title="Delete group" aria-label={`Delete ${group.component} ${group.operator} group`} onClick={() => remove("groups", group.id)}><Trash2 size={16} aria-hidden="true" /></button>
        </li>)}</ul>
        <GroupForm state={inputs.data} disabled={disabled} save={body => save(w => w.group(body))} />
      </section>
      <InventoryForm state={inputs.data} disabled={disabled} save={body => save(w => w.inventory(body))} />
    </div>}
    {action.isPending && <p role="status">Saving reviewed inputs...</p>}
    {action.isSuccess && <p role="status">Reviewed input saved. Matching runs are not refreshed automatically.</p>}
  </div>;
}

function GroupForm({ state, disabled, save }: { state: JobInputs; disabled: boolean; save: (body: GroupBody) => Promise<void> }) {
  const [component, setComponent] = useState<GroupBody["component"]>("R");
  const used = new Set(state.members.map(m => m.job_skill_id || m.job_matching_fact_id));
  const sources = [...state.skills.map(x => ({ id: x.id, label: x.raw_text, type: x.skill_type, review: x.review_status, fact: false })),
    ...state.facts.map(x => ({ id: x.id, label: x.statement, type: x.fact_type, review: x.review_status, fact: true }))]
    .filter(x => !used.has(x.id) && x.review === "approved" && (component === "Q" ? ["qualification", "experience"].includes(x.type) : ["skill", "tool", "domain_knowledge", "language"].includes(x.type)));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const selected = data.getAll("member").map(String);
    const operator = String(data.get("operator")) as GroupBody["operator"];
    if (!selected.length || (operator === "SINGLE" && selected.length !== 1)) { setError("Select one member for SINGLE, or one or more distinct members for OR/AND."); return; }
    setError("");
    await save({ component, operator, classification: String(data.get("classification")) as Classification,
      critical: component === "R" && data.get("critical") === "on", review_status: String(data.get("review")) as Review,
      members: selected.map(id => sources.find(x => x.id === id)!.fact ? { job_skill_id: null, job_matching_fact_id: id } : { job_skill_id: id, job_matching_fact_id: null }) });
  }
  const [error, setError] = useState("");
  return <form onSubmit={e => { void submit(e).catch(() => undefined); }}><fieldset disabled={disabled} className="match-form">
    <legend>Add one-level group</legend>
    <Field label="Component"><Options values={["R", "P", "Q"]} value={component} onChange={e => setComponent(e.target.value as GroupBody["component"])} /></Field>
    <Field label="Operator"><Options name="operator" values={["SINGLE", "OR", "AND"]} /></Field>
    <Field label="Group classification"><Options key={component} name="classification" values={component === "R" ? ["required"] : component === "P" ? ["preferred"] : ["required", "preferred"]} /></Field>
    <Field label="Group review status"><Options name="review" values={reviews} /></Field>
    {component === "R" && <label><input name="critical" type="checkbox" /> Explicitly reviewed critical requirement (requires approved group)</label>}
    <fieldset className="match-members"><legend>Approved, ungrouped members</legend>{sources.map(x => <label key={x.id}><input name="member" value={x.id} type="checkbox" />{x.label} · {x.type}</label>)}{sources.length === 0 && <p>No eligible ungrouped members.</p>}</fieldset>
    {error && <p role="alert">{error}</p>}
    <button type="submit" disabled={!sources.length}><Plus size={16} aria-hidden="true" />Add group</button>
  </fieldset></form>;
}

function InventoryForm({ state, disabled, save }: { state: JobInputs; disabled: boolean; save: (body: InventoryBody) => Promise<void> }) {
  const [o, setO] = useState<Applicability>(state.inventory?.o_applicability || "unknown");
  const [q, setQ] = useState<Applicability>(state.inventory?.q_applicability || "unknown");
  return <section className="match-section"><h2>Inventory sign-off and applicability</h2>
    <p>Completeness requires source review, resolved classifications, approved groups and attributed applicability. Absence of extracted terms is not evidence of completeness.</p>
    <form onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget);
      void save({ review_status: String(data.get("review")) as Review, inventory_complete: data.get("complete") === "on",
        o_applicability: o, q_applicability: q, o_reason: o === "not_applicable" ? "no_occupation_scope_stated" : null,
        q_reason: q === "not_applicable" ? "no_qualification_or_experience_scope_stated" : null }).catch(() => undefined);
    }}><fieldset disabled={disabled} className="match-form">
      <Field label="Occupation applicability"><Options values={["unknown", "applicable", "not_applicable"]} value={o} onChange={e => setO(e.target.value as Applicability)} /></Field>
      {o === "not_applicable" && <p>Reason: no_occupation_scope_stated. This is an explicit reviewed decision.</p>}
      <Field label="Qualification/experience applicability"><Options values={["unknown", "applicable", "not_applicable"]} value={q} onChange={e => setQ(e.target.value as Applicability)} /></Field>
      {q === "not_applicable" && <p>Reason: no_qualification_or_experience_scope_stated. This is an explicit reviewed decision.</p>}
      <Field label="Inventory review status"><Options name="review" values={reviews} defaultValue={state.inventory?.review_status || "pending"} /></Field>
      <label><input name="complete" type="checkbox" defaultChecked={state.inventory_current && state.inventory?.inventory_complete || false} /> I reviewed the source and confirm this inventory is complete.</label>
      <button type="submit"><Check size={16} aria-hidden="true" />Save inventory review</button>
    </fieldset></form>
  </section>;
}

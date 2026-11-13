import type { Atomic, Evidence, MatchingRun, MatchResult } from "../../types/matching";

export function atomicIndex(run: MatchingRun) {
  return new Map(run.results.flatMap(result => result.gaps.flatMap(gap => gap.atomic_assessments.map(atom => [atom.id, atom] as const))));
}
export function resolveEvidence(atom: Atomic, side: "candidate" | "requirement", index: Map<string, Atomic>): Evidence | undefined {
  const direct = atom.reason_parameters[`${side}_evidence`];
  if (direct) return direct;
  const anchor = atom.reason_parameters[`${side}_evidence_anchor_id`];
  return anchor ? index.get(anchor)?.reason_parameters[`${side}_evidence`] : undefined;
}
const names: Record<string, string> = { R: "Required skills", P: "Preferred skills", O: "Occupation", Q: "Qualification / experience" };
export const readable = (value: string) => value.replace(/_/g, " ");
function Reasons({ items }: { items?: string[] }) {
  return items?.length ? <ul className="match-reasons">{items.map((x, i) => <li key={`${x}:${i}`}>{readable(x)} <code>{x}</code></li>)}</ul> : null;
}
export function EvidenceText({ value, candidate }: { value?: Evidence; candidate: boolean }) {
  return <div className="match-evidence"><h4>{candidate ? "Candidate-confirmed evidence" : "Reviewed job evidence"}</h4>
    {!value || value.source_record_missing ? <p>Evidence unavailable or redacted. Do not infer support.</p> : <>
      <p><strong>{value.raw_text || value.statement || value.normalized_text || "Referenced evidence"}</strong></p>
      {value.evidence_sentence && <blockquote>{value.evidence_sentence}</blockquote>}
      {value.evidence_reference && <p>Source reference: {value.evidence_reference}</p>}
      <p>{value.review_status || "Review status unavailable"} · {value.skill_type || value.fact_type}</p>
      {value.completion && <p>Qualification completion: {readable(value.completion)}</p>}
      {value.duration_months != null && <p>Duration: {value.duration_months} months</p>}
      {value.field && <p>Field: {value.field}</p>}{value.scope && <p>Scope: {value.scope}</p>}
      {value.extraction_provenance && <p className="match-muted">{value.extraction_provenance.source_section || "Section unspecified"} · character offsets {value.extraction_provenance.start_char ?? "?"}–{value.extraction_provenance.end_char ?? "?"} · {value.extraction_provenance.extraction_method}</p>}
      <details><summary>Evidence provenance</summary><dl className="match-provenance"><dt>Occurrence / fact</dt><dd>{value.id || "Unavailable"}</dd><dt>Extracted term</dt><dd>{value.extracted_term_id || "Not applicable"}</dd><dt>Source</dt><dd>{value.source || value.cv_document_id || "Reviewed fact"}</dd></dl>
        {value.taxonomy_links?.map(link => <p key={`${link.release_id}:${link.concept_id}`}>Reviewed concept {link.concept_id} · release {link.release_id} · {link.match_method}</p>)}
      </details>
      {(value.full_source_required_for_text_reconstruction || Object.keys(value.text_omissions || {}).length > 0) && <p className="match-warning">Bounded excerpt: content was omitted or clipped. Full source is needed for reconstruction.</p>}
    </>}
  </div>;
}

export function RunDetails({ run, jobNames }: { run: MatchingRun; jobNames: Map<string, string> }) {
  const index = atomicIndex(run);
  const replayable = run.status !== "unreplayable";
  return <>
    <section className="match-section" aria-label="Run readiness">
      <div className="match-summary"><div><h2>{readable(run.status)} run</h2><p>{new Date(run.created_at).toLocaleString()}</p></div>
        <p>{run.readiness.score_ready_jobs} score-ready · {run.readiness.provisional_jobs} provisional</p></div>
      {!run.current && <p role="status" className="match-warning">Not current. No historical score is presented as a current alignment.</p>}
      {!replayable && <p role="alert">Deleted or redacted evidence: this run is unreplayable. Sensitive explanations are unavailable.</p>}
      {!run.readiness.ranking_evaluation_ready && <p className="match-warning">UI-only ordering. An incomplete or provisional pool is not an evaluated ranking.</p>}
      <Reasons items={run.readiness.warnings} />
      <p>Eligible jobs: {run.retrieval.eligible_job_count}. Missing/stale job embeddings now: {run.retrieval.stale_missing_job_count} (recorded: {run.retrieval.recorded_stale_missing_job_count}). Pool limit: {run.retrieval.pool_limit}.</p>
      {run.retrieval.stale_missing_job_count > 0 && <p className="match-warning">The retrieved universe is incomplete. Retrieval ranks exclude missing/stale embeddings.</p>}
      <details><summary>Policy and retrieval provenance</summary><dl className="match-provenance">
        <dt>Policy</dt><dd>{run.policy_version}</dd><dt>Policy SHA-256</dt><dd>{run.policy_hash}</dd>
        <dt>Engine</dt><dd>{run.engine_version}</dd><dt>Input fingerprint</dt><dd>{run.input_fingerprint}</dd>
        <dt>Template</dt><dd>{run.retrieval.template_version}</dd><dt>Model</dt><dd>{run.retrieval.model_id}</dd>
        <dt>Revision</dt><dd>{run.retrieval.model_revision}</dd><dt>Ordering</dt><dd>{readable(run.ordering)}</dd>
      </dl></details>
    </section>
    {run.results.length === 0 && <p>No jobs were returned in this run.</p>}
    {run.results.map((result, i) => <Result key={result.result_id} result={result} index={index} title={result.job_id ? jobNames.get(result.job_id) || "Job metadata unavailable" : "Deleted job"} position={i + 1} visible={run.current && result.current && replayable} replayable={replayable && result.status !== "unreplayable"} />)}
  </>;
}

function Result({ result, index, title, position, visible, replayable }: { result: MatchResult; index: Map<string, Atomic>; title: string; position: number; visible: boolean; replayable: boolean }) {
  const score = visible && !result.provisional ? result.alignment_score : null;
  return <article className="match-result">
    <div className="match-summary"><div><p className="match-muted">Position {position} · {readable(result.status)}</p><h2>{title}</h2></div>
      <div><strong className="match-score">{score === null ? "Unavailable" : `${score} / 100`}</strong><p>Structured alignment</p></div></div>
    <p>Retrieval rank {result.original_retrieval_rank} · Dense similarity {result.retrieval_similarity} · Numeric alignment weight: 0</p>
    <p className="match-muted">Alignment and similarity are decision-support evidence, not hiring probabilities. Missing means unsupported under the policy, not proof of inability.</p>
    <p>{readable(result.reason_code)}</p>
    {result.provisional && <p className="match-warning">Provisional: missing or unassessed inputs. Null is not zero.</p>}
    <Reasons items={result.reason_parameters.readiness_reasons} /><Reasons items={result.reason_parameters.warnings} />
    {result.reason_parameters.consistency_message && <p>{result.reason_parameters.consistency_message}</p>}
    {result.reason_parameters.unknown_occurrence_summary && <p>Unknown-classification occurrences: {result.reason_parameters.unknown_occurrence_summary.total}. Visible and unscored.</p>}
    {!replayable ? <p>Evidence was redacted; this history cannot be replayed.</p> : <details><summary>Components, gaps and evidence</summary>
      {!visible && <p className="match-warning">Recorded components below are historical diagnostics, not current scores.</p>}
      <div className="match-table-scroll"><table><caption>Structured components (base weights 7:3:2:1)</caption><thead><tr><th>Component</th><th>Applicability / status</th><th>Value</th><th>Coverage</th><th>Base / effective weight</th><th>Reason</th></tr></thead>
        <tbody>{result.components.map(component => <tr key={component.component}>
          <th scope="row">{names[component.component] || component.component}</th><td>{readable(component.applicability)} / {readable(component.status)}</td>
          <td>{component.value_fraction ?? "Unassessed"}</td><td>{component.coverage_fraction ?? "Unknown"}</td>
          <td>{component.base_weight} / {component.effective_weight_fraction ?? "Unavailable"}</td><td>{readable(component.reason_code)}</td>
        </tr>)}</tbody></table></div>
      <p>Exact alignment: {visible ? result.alignment_fraction ?? "Unavailable" : "Not current"}. Critical deduction: {result.reason_parameters.critical_deduction_fraction ?? "Unassessed"}.</p>
      {result.gaps.map((gap, n) => <details key={`${gap.group_id}:${n}`} className="match-gap"><summary>{gap.status} · {gap.reason_parameters.component || "Unscored occurrence"} · {readable(gap.reason_code)}{gap.critical ? " · critical" : ""}</summary>
        <p>Support: {gap.support_fraction ?? "Unknown"}. {gap.reason_parameters.operator || "Atomic assessment"}</p>
        <Reasons items={gap.reason_parameters.warnings} />
        {((gap.evidence.candidate_reference_summary?.omitted_count || 0) + (gap.evidence.requirement_reference_summary?.omitted_count || 0) > 0) && <p>Evidence summary references are bounded; individual assessment references are shown below.</p>}
        {gap.atomic_assessments.map(atom => <div key={atom.id} className="match-atomic">
          <p><strong>{readable(atom.reason_code)}</strong> · {atom.support_fraction ?? "Unknown support"}</p>
          {atom.reason_parameters.explanation && <p>{atom.reason_parameters.explanation}</p>}
          <div className="match-evidence-grid"><EvidenceText candidate value={resolveEvidence(atom, "candidate", index)} /><EvidenceText candidate={false} value={resolveEvidence(atom, "requirement", index)} /></div>
        </div>)}
      </details>)}
    </details>}
  </article>;
}

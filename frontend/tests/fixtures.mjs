export const fingerprint = "a".repeat(64);
export const user = { id: "user-synthetic", email: "synthetic@example.test", full_name: "Synthetic Candidate", status: "active", roles: [{ name: "candidate" }] };
export const fact = { id: "fact-synthetic", fact_type: "qualification", statement: "Synthetic unfinished qualification", completion: "in_progress", duration_months: null, field: "Computing", scope: "Supervised study", evidence_reference: "Synthetic line 2", review_status: "pending" };
export const candidate = { fingerprint, profile: { id: "profile-synthetic", status: "active" }, facts: [fact], sources: [{ id: "cv-synthetic" }] };
export const jobs = [{ id: "job-synthetic", title: "Synthetic Software Role", company: "Fixture Company", description: "Synthetic duties and requirements only.", sections: [], status: "processed" }];
const atom = { id: "atom-anchor", support_fraction: "1/1", reason_code: "text_only_match", reason_parameters: {
  explanation: "Reviewed text and type match; text-only evidence.",
  candidate_evidence: { id: "candidate-occurrence", raw_text: "Python", review_status: "approved", skill_type: "tool", evidence_sentence: "Synthetic Python evidence." },
  requirement_evidence: { id: "job-occurrence", raw_text: "Python", review_status: "approved", skill_type: "skill", evidence_sentence: "Synthetic Python requirement.", text_omissions: { evidence_sentence: {} } },
} };
export const run = {
  run_id: "run-synthetic", policy_version: "matching-policy-v1", policy_hash: fingerprint, engine_version: "v1", status: "current", current: true, created_at: "2026-11-13T12:00:00Z", input_fingerprint: fingerprint,
  retrieval: { template_version: "e5-job-profile-v2", model_id: "synthetic-offline", model_revision: "synthetic-revision", pool_limit: 20, stale_missing_job_count: 2, recorded_stale_missing_job_count: 1, eligible_job_count: 4 },
  readiness: { warnings: ["eligible_universe_incomplete"], score_ready_jobs: 1, provisional_jobs: 1, ranking_evaluation_ready: false }, ordering: "UI-only scored-first ordering; not an evaluated ranking",
  results: [{ result_id: "result-ready", job_id: jobs[0].id, current: true, status: "ready", provisional: false, alignment_score: "76.92", alignment_fraction: "1000/13", original_retrieval_rank: 2, retrieval_similarity: "0.875000", reason_code: "candidate_confirmed_alignment", reason_parameters: { critical_deduction_fraction: "0/1" },
    components: ["R", "P", "O", "Q"].map((component, i) => ({ component, applicability: "applicable", status: "assessed", numerator: i < 2 ? "1" : "0", denominator: "1", base_weight: [7, 3, 2, 1][i], effective_weight_fraction: `${[7, 3, 2, 1][i]}/13`, value_fraction: i < 2 ? "1/1" : "0/1", coverage_fraction: "1/1", contribution_fraction: i < 2 ? `${[7, 3, 2, 1][i]}/13` : "0/1", reason_code: "assessed" })),
    gaps: [{ group_id: "group-synthetic", status: "Matched", critical: false, support_fraction: "1/1", reason_code: "text_only_match", reason_parameters: { component: "R", operator: "SINGLE" }, evidence: {}, atomic_assessments: [atom] }] },
    { result_id: "result-provisional", job_id: null, current: true, status: "provisional", provisional: true, alignment_score: null, alignment_fraction: null, original_retrieval_rank: 1, retrieval_similarity: "0.950000", reason_code: "assessment_incomplete", reason_parameters: { readiness_reasons: ["inventory_incomplete"], unknown_occurrence_summary: { total: 1, omitted_count: 0 } }, components: [],
      gaps: [{ group_id: null, status: "unassessed", critical: false, support_fraction: null, reason_code: "unknown_classification", reason_parameters: {}, evidence: {}, atomic_assessments: [{ id: "atom-referenced", support_fraction: null, reason_code: "identity_incomparable", reason_parameters: { candidate_evidence_anchor_id: atom.id } }] }] }],
};
export const inventory = { fingerprint, source_fingerprint: fingerprint, facts: [], groups: [], members: [], occurrences: [], inventory: null, inventory_current: false,
  skills: [{ id: "skill-synthetic", raw_text: "Python", normalized_text: "python", skill_type: "skill", review_status: "approved", requirement_type: "required", evidence_sentence: "Synthetic required Python evidence." },
    { id: "pending-skill", raw_text: "Unknown tool", normalized_text: "unknown tool", skill_type: "tool", review_status: "pending", requirement_type: "unknown", evidence_sentence: "Synthetic ambiguous text." }] };

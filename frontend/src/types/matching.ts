export type Review = "approved" | "pending" | "rejected";
export type Classification = "required" | "preferred" | "non_requirement" | "unknown";
export type Applicability = "applicable" | "not_applicable" | "unknown";
export type Fact = {
  id: string; fact_type: "occupation" | "qualification" | "experience";
  statement: string; completion: string; duration_months: number | null;
  field: string; scope: string; evidence_reference: string; review_status: Review;
  cv_document_id?: string | null; taxonomy_concept_id?: string | null; taxonomy_release_id?: string | null;
};
export type FactBody = Omit<Fact, "id">;
export type SkillInput = {
  id: string; raw_text: string; normalized_text: string; skill_type: string;
  requirement_type: Classification; review_status: Review; evidence_sentence: string;
};
export type Group = {
  id: string; component: "R" | "P" | "Q"; operator: "SINGLE" | "OR" | "AND";
  classification: Classification; critical: boolean; review_status: Review;
};
export type Member = { group_id?: string; job_skill_id: string | null; job_matching_fact_id: string | null };
export type GroupBody = Omit<Group, "id"> & { members: Member[] };
export type InventoryBody = {
  review_status: Review; inventory_complete: boolean;
  o_applicability: Applicability; o_reason: "no_occupation_scope_stated" | null;
  q_applicability: Applicability; q_reason: "no_qualification_or_experience_scope_stated" | null;
};
export type CandidateInputs = {
  fingerprint: string; profile: { id: string; status: string }; facts: Fact[];
  sources: { id: string }[];
};
export type JobInputs = {
  fingerprint: string; source_fingerprint: string; skills: SkillInput[]; facts: Fact[];
  groups: Group[]; members: Member[];
  occurrences: { job_skill_id: string; classification: Classification; review_status: Review; reason: string }[];
  inventory: InventoryBody | null; inventory_current: boolean;
};
export type Evidence = {
  id?: string; raw_text?: string; normalized_text?: string; statement?: string;
  evidence_sentence?: string; evidence_reference?: string; skill_type?: string;
  fact_type?: string; review_status?: string; completion?: string; scope?: string;
  duration_months?: number | null; field?: string; source_record_missing?: boolean;
  extracted_term_id?: string; cv_document_id?: string; source?: string;
  taxonomy_links?: { concept_id: string; release_id: string; match_method?: string }[];
  text_omissions?: Record<string, unknown>; full_source_required_for_text_reconstruction?: boolean;
  extraction_provenance?: { source_section?: string; start_char?: number; end_char?: number; extraction_method?: string };
};
export type Atomic = {
  id: string; reason_code: string; support_fraction: string | null;
  reason_parameters: {
    explanation?: string; candidate_evidence?: Evidence; requirement_evidence?: Evidence;
    candidate_evidence_anchor_id?: string; requirement_evidence_anchor_id?: string;
  };
};
export type Gap = {
  group_id: string | null; status: string; critical: boolean; support_fraction: string | null;
  reason_code: string; reason_parameters: { component?: string; operator?: string; warnings?: string[] };
  evidence: { candidate_reference_summary?: { omitted_count: number }; requirement_reference_summary?: { omitted_count: number } };
  atomic_assessments: Atomic[];
};
export type Component = {
  component: string; status: string; applicability: Applicability; numerator: string | null; denominator: string | null;
  base_weight: number; effective_weight_fraction: string | null; value_fraction: string | null;
  coverage_fraction: string | null; contribution_fraction: string | null; reason_code: string;
};
export type MatchResult = {
  result_id: string; job_id: string | null; current: boolean; status: string; provisional: boolean;
  alignment_score: string | null; alignment_fraction: string | null;
  original_retrieval_rank: number; retrieval_similarity: string; reason_code: string;
  reason_parameters: { readiness_reasons?: string[]; warnings?: string[]; consistency_message?: string;
    critical_deduction_fraction?: string | null; unknown_occurrence_summary?: { total: number; omitted_count: number } };
  components: Component[]; gaps: Gap[];
};
export type MatchingRun = {
  run_id: string; policy_version: string; policy_hash: string; engine_version: string;
  status: string; current: boolean; created_at: string; input_fingerprint: string;
  retrieval: { template_version: string; model_id: string; model_revision: string; pool_limit: number;
    stale_missing_job_count: number; recorded_stale_missing_job_count: number; eligible_job_count: number };
  readiness: { warnings: string[]; score_ready_jobs: number; provisional_jobs: number; ranking_evaluation_ready: boolean };
  ordering: string; results: MatchResult[];
};

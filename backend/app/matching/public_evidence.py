"""Candidate-visible JSON contracts. Unknown fields fail closed, including history."""


def fields(names: str) -> dict:
    return dict.fromkeys(names.split(), True)


def project(value, schema):
    """Copy only declared fields/shapes; never mutate a persisted snapshot."""
    if value is None:
        return None
    if schema is True:
        return None if isinstance(value, (dict, list, tuple)) else value
    if isinstance(schema, list):
        return [project(item, schema[0]) for item in value] if isinstance(value, (list, tuple)) else []
    if not isinstance(value, dict):
        return {}
    return {key: project(value[key], child) for key, child in schema.items() if key in value}


REVIEW = fields("id review_status reviewer_pseudonym_snapshot reviewer_role_snapshot reviewed_at source_fingerprint")
REFERENCE = fields("id source_kind anchor_atomic_id source_snapshot_sha256 extracted_term_id")
SUMMARY = fields("total omitted_count complete_sequence_sha256 complete_records_in")
TEXT_FIELDS = "raw_text normalized_text statement scope field evidence_sentence"
EVIDENCE = fields(
    "id extracted_term_id raw_text normalized_text skill_type fact_type statement completion duration_months "
    "field scope evidence_reference evidence_sentence review_status cv_document_id taxonomy_concept_id "
    "taxonomy_release_id source_fingerprint reviewer_pseudonym_snapshot reviewer_role_snapshot reviewed_at "
    "source_record_missing candidate_profile_id job_id source confidence_score provenance origin classification "
    "cleaned_description_sha256 capability_start capability_end evidence_start evidence_end "
    "source_snapshot_sha256 full_source_required_for_text_reconstruction"
)
EVIDENCE.update({
    "comparison_fingerprints": fields("normalized_text statement field scope"),
    "extraction_provenance": fields("id extraction_method source_section start_char end_char"),
    "taxonomy_links": [fields("concept_id release_id match_method taxonomy_confidence")],
    "text_omissions": {key: fields("original_sha256 original_characters retained_characters") for key in TEXT_FIELDS.split()},
})
ATOMIC = fields(
    "group_id component member_id requirement_id candidate_id support reason_code classification explanation "
    "candidate_extracted_term_id requirement_extracted_term_id requirement_origin "
    "candidate_evidence_reference requirement_evidence_reference candidate_evidence_anchor_id requirement_evidence_anchor_id"
)
ATOMIC.update({"candidate_evidence": EVIDENCE, "requirement_evidence": EVIDENCE})
GAP_EVIDENCE = {
    "group_id": True, "candidate_confirmed_evidence": [REFERENCE], "reviewed_requirements": [REFERENCE],
    "candidate_reference_summary": SUMMARY, "requirement_reference_summary": SUMMARY,
    "group_review": REVIEW | fields("operator classification critical"),
}
GAP_REASONS = {**fields("component operator"), "warnings": [True]}
COMPONENT_REASONS = fields("coverage_fraction contribution_fraction")
RESULT_REASONS = fields(
    "evidence_snapshot_version consistency_message critical_missing_support critical_penalty_cap_fraction critical_deduction_fraction"
)
RESULT_REASONS.update({
    "readiness_reasons": [True], "warnings": [True], "unknown_occurrences": [ATOMIC],
    "unknown_occurrence_summary": SUMMARY, "occupation_summary": SUMMARY,
    "occupation_assessments": [fields("requirement_id candidate_id support reason_code")],
    "consistency_reference": fields("group_id occurrence_id extracted_term_id component classification"),
    "inventory_review": REVIEW | fields("inventory_complete o_applicability o_reason q_applicability q_reason"),
})
EMBEDDING = fields(
    "id candidate_profile_id job_id model_id model_revision template_version source_hash taxonomy_fingerprint "
    "status indexed_at created_at updated_at vector_sha256"
)
PROVENANCE = fields(
    "input_adapter_version candidate_hash candidate_representation_source_hash missing_job_embeddings "
    "stale_job_embeddings eligible_jobs model_id model_revision template_version engine_version policy_hash "
    "engine_fingerprint full_universe_fingerprint capture_fingerprint"
)
PROVENANCE.update({
    "candidate_embedding": EMBEDDING,
    "taxonomy_selection": [fields("id fingerprint")],
    "universe": [{**fields("job_id reviewed_input_hash inventory_hash representation_source_hash representation_sha256"),
                  "embedding": EMBEDDING}],
    "retrieval_order": [fields("rank job_id retrieval_similarity candidate_input_hash job_input_hash")],
})

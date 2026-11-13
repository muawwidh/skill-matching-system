"""Component arithmetic, hash-only run provenance and atomic input invalidation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_matching_input_integrity"
down_revision = "0009_explainable_matching"
branch_labels = None
depends_on = None

INPUT_LOCK_KEY = 603402

# Scope is deliberately conservative for retrieval-universe/taxonomy changes.
INPUT_TABLES = {
    "candidate_profiles": "profile",
    "candidate_skills": "candidate",
    "cv_documents": "candidate",
    "cv_sections": "cv",
    "extracted_candidate_terms": "cv",
    "candidate_matching_facts": "candidate",
    "candidate_profile_embeddings": "candidate",
    "job_matching_facts": "job",
    "job_requirement_groups": "job",
    "job_requirement_group_members": "job",
    "job_inventory_reviews": "job",
    "job_occurrence_reviews": "job",
    "jobs": "all",
    "job_sections": "all",
    "job_skills": "all",
    "extracted_job_terms": "all",
    "job_embeddings": "all",
    "taxonomy_sources": "all",
    "taxonomy_versions": "all",
    "taxonomy_concepts": "all",
    "taxonomy_labels": "all",
    "taxonomy_relationships": "all",
    "occupations": "all",
    "onet_data_records": "all",
    "esco_onet_mappings": "all",
    "approved_taxonomy_links": "all",
    "taxonomy_link_candidates": "all",
}


def upgrade():
    op.create_check_constraint("ck_critical_required_skill", "job_requirement_groups",
        "NOT critical OR (component = 'R' AND classification = 'required' AND review_status = 'approved')")
    op.create_check_constraint("ck_component_ratio_null", "match_score_components",
        "(numerator IS NULL) = (value_fraction IS NULL) AND "
        "(denominator IS NULL) = (value_fraction IS NULL) AND "
        "(value IS NULL) = (value_fraction IS NULL)")
    # Compare exact integer products, not a rounded division. Equivalent unreduced
    # pairs are legitimate (e.g. 2/6 with canonical value_fraction='1/3').
    op.create_check_constraint("ck_component_ratio_exact", "match_score_components",
        "CASE WHEN value_fraction IS NULL THEN true ELSE "
        "numerator >= 0 AND denominator < 'Infinity'::numeric AND numerator <= denominator AND "
        "numerator * split_part(value_fraction, '/', 2)::numeric = "
        "denominator * split_part(value_fraction, '/', 1)::numeric END")
    for name, size in (("engine_version", 80), ("model_id", 160), ("model_revision", 64),
                       ("template_version", 40), ("taxonomy_fingerprint", 64), ("retrieval_fingerprint", 64)):
        op.add_column("matching_runs", sa.Column(name, sa.String(size), nullable=True))
    op.add_column("matching_runs", sa.Column("provenance_snapshot", postgresql.JSONB(), nullable=True))
    op.create_check_constraint("ck_run_provenance_bound", "matching_runs",
        "provenance_snapshot IS NULL OR length(CAST(provenance_snapshot AS TEXT)) <= 262144")
    op.execute(f"""
    CREATE FUNCTION phase6_input_gate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM pg_advisory_xact_lock({INPUT_LOCK_KEY});
      RETURN NULL;
    END $$;
    CREATE FUNCTION phase6_invalidate_inputs() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE previous jsonb; following jsonb; owners uuid[]; affected uuid[];
    BEGIN
      IF TG_OP <> 'INSERT' THEN previous := to_jsonb(OLD); END IF;
      IF TG_OP <> 'DELETE' THEN following := to_jsonb(NEW); END IF;
      IF previous = following THEN RETURN NULL; END IF;
      IF TG_ARGV[0] = 'profile' THEN
        owners := ARRAY[(previous->>'id')::uuid, (following->>'id')::uuid];
      ELSIF TG_ARGV[0] = 'candidate' THEN
        owners := ARRAY[(previous->>'candidate_profile_id')::uuid, (following->>'candidate_profile_id')::uuid];
      ELSIF TG_ARGV[0] = 'cv' THEN
        SELECT array_agg(candidate_profile_id) INTO owners FROM cv_documents
          WHERE id IN ((previous->>'cv_document_id')::uuid, (following->>'cv_document_id')::uuid);
      ELSIF TG_ARGV[0] = 'job' THEN
        owners := ARRAY[(previous->>'job_id')::uuid, (following->>'job_id')::uuid];
      END IF;
      SELECT array_agg(r.id) INTO affected FROM matching_runs r
        WHERE r.is_current AND r.status = 'current' AND (
          TG_ARGV[0] = 'all'
          OR (TG_ARGV[0] IN ('profile','candidate','cv') AND r.candidate_profile_id = ANY(owners))
          OR (TG_ARGV[0] = 'job' AND EXISTS (
            SELECT 1 FROM job_match_results j WHERE j.run_id = r.id AND j.job_id = ANY(owners))));
      UPDATE job_match_results SET status = 'stale' WHERE run_id = ANY(affected);
      UPDATE matching_runs SET status = 'stale', is_current = false WHERE id = ANY(affected);
      RETURN NULL;
    END $$;
    """)
    for table, scope in INPUT_TABLES.items():
        op.execute(f"CREATE TRIGGER phase6_input_gate BEFORE INSERT OR UPDATE OR DELETE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION phase6_input_gate()")
        op.execute(f"CREATE TRIGGER phase6_input_invalidate AFTER INSERT OR UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION phase6_invalidate_inputs('{scope}')")


def downgrade():
    op.drop_constraint("ck_critical_required_skill", "job_requirement_groups", type_="check")
    for table in INPUT_TABLES:
        op.execute(f"DROP TRIGGER phase6_input_invalidate ON {table}")
        op.execute(f"DROP TRIGGER phase6_input_gate ON {table}")
    op.execute("DROP FUNCTION phase6_invalidate_inputs()")
    op.execute("DROP FUNCTION phase6_input_gate()")
    op.drop_constraint("ck_run_provenance_bound", "matching_runs", type_="check")
    for name in ("provenance_snapshot", "retrieval_fingerprint", "taxonomy_fingerprint", "template_version",
                 "model_revision", "model_id", "engine_version"):
        op.drop_column("matching_runs", name)
    op.drop_constraint("ck_component_ratio_exact", "match_score_components", type_="check")
    op.drop_constraint("ck_component_ratio_null", "match_score_components", type_="check")

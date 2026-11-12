"""Reviewed explainable matching inputs and future results, separate from legacy scores."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Text
from uuid import UUID

revision = "0009_explainable_matching"
down_revision = "0008_dense_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION phase6_fraction_valid(exact text, projected numeric) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE AS $$
    DECLARE n numeric; d numeric; a numeric; b numeric; r numeric; rounded numeric;
    BEGIN
      IF exact IS NULL OR projected IS NULL THEN RETURN exact IS NULL AND projected IS NULL; END IF;
      IF exact !~ '^(-?(0|[1-9][0-9]*))/([1-9][0-9]*)$' OR exact LIKE '-0/%' THEN RETURN false; END IF;
      n := split_part(exact,'/',1)::numeric; d := split_part(exact,'/',2)::numeric;
      a := abs(n); b := d;
      WHILE b <> 0 LOOP r := mod(a,b); a := b; b := r; END LOOP;
      IF a <> 1 THEN RETURN false; END IF;
      rounded := div(abs(n)*1000000,d);
      IF 2*mod(abs(n)*1000000,d) >= d THEN rounded := rounded+1; END IF;
      RETURN projected = sign(n)*rounded/1000000;
    END $$;
    """)
    op.create_table('scoring_configurations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.String(length=80), nullable=False),
    sa.Column('canonical_json', sa.Text(), nullable=False),
    sa.Column('policy_hash', sa.String(length=64), nullable=False),
    sa.Column('engine_version', sa.String(length=80), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('policy_hash'),
    sa.UniqueConstraint('version')
    )
    op.execute("""
    CREATE FUNCTION phase6_policy_insert() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE body jsonb;
    BEGIN
      body := NEW.canonical_json::jsonb;
      IF jsonb_typeof(body) <> 'object' OR body->>'policy_version' IS DISTINCT FROM NEW.version
         OR NEW.engine_version = '' OR NEW.version = ''
         OR NEW.policy_hash IS DISTINCT FROM encode(sha256(convert_to(NEW.canonical_json,'UTF8')),'hex') THEN
        RAISE EXCEPTION 'Invalid immutable policy identity/hash';
      END IF;
      IF NEW.version = 'matching-policy-v1' AND (
        body->'relationship_allowlist' IS DISTINCT FROM '[]'::jsonb
        OR NEW.engine_version <> 'matching-policy-v1'
        OR NEW.policy_hash <> '2a5d9dfb400be9fdea31544e5083f2876fcf685ab41037daa24ef45ce035c8c2'
      ) THEN RAISE EXCEPTION 'Invalid matching-policy-v1 canonical bytes/configuration'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase6_policy_insert_guard BEFORE INSERT ON scoring_configurations
      FOR EACH ROW EXECUTE FUNCTION phase6_policy_insert();
    """)
    op.create_table('job_inventory_reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('inventory_complete', sa.Boolean(), nullable=False),
    sa.Column('o_applicability', sa.String(length=20), nullable=False),
    sa.Column('o_reason', sa.String(length=80), nullable=True),
    sa.Column('q_applicability', sa.String(length=20), nullable=False),
    sa.Column('q_reason', sa.String(length=80), nullable=True),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_pseudonym_snapshot', sa.String(length=80), nullable=False),
    sa.Column('reviewer_role_snapshot', sa.String(length=120), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(o_applicability = 'not_applicable' AND o_reason IS NOT NULL AND o_reason = 'no_occupation_scope_stated') OR (o_applicability <> 'not_applicable' AND o_reason IS NULL)", name='ck_o_reason'),
    sa.CheckConstraint("(q_applicability = 'not_applicable' AND q_reason IS NOT NULL AND q_reason = 'no_qualification_or_experience_scope_stated') OR (q_applicability <> 'not_applicable' AND q_reason IS NULL)", name='ck_q_reason'),
    sa.CheckConstraint("NOT inventory_complete OR (review_status = 'approved' AND o_applicability <> 'unknown' AND q_applicability <> 'unknown')", name='ck_inventory_complete'),
    sa.CheckConstraint("o_applicability IN ('applicable', 'not_applicable', 'unknown')", name='ck_o_applicability'),
    sa.CheckConstraint("q_applicability IN ('applicable', 'not_applicable', 'unknown')", name='ck_q_applicability'),
    sa.CheckConstraint("review_status IN ('approved', 'pending', 'rejected')", name='ck_review_status'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id')
    )
    op.create_table('job_matching_facts',
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fact_type', sa.String(length=30), nullable=False),
    sa.Column('statement', sa.String(length=1000), nullable=False),
    sa.Column('completion', sa.String(length=20), nullable=False),
    sa.Column('duration_months', sa.Integer(), nullable=True),
    sa.Column('field', sa.String(length=255), nullable=False),
    sa.Column('scope', sa.String(length=500), nullable=False),
    sa.Column('evidence_reference', sa.String(length=255), nullable=False),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_pseudonym_snapshot', sa.String(length=80), nullable=False),
    sa.Column('reviewer_role_snapshot', sa.String(length=120), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("completion IN ('unknown', 'completed', 'in_progress', 'not_completed', 'not_applicable')", name='ck_completion'),
    sa.CheckConstraint("fact_type IN ('occupation', 'qualification', 'experience')", name='ck_fact_type'),
    sa.CheckConstraint("review_status IN ('approved', 'pending', 'rejected')", name='ck_review_status'),
    sa.CheckConstraint('duration_months IS NULL OR duration_months >= 0', name='ck_duration'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('job_requirement_groups',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('component', sa.String(length=1), nullable=False),
    sa.Column('operator', sa.String(length=10), nullable=False),
    sa.Column('classification', sa.String(length=30), nullable=False),
    sa.Column('critical', sa.Boolean(), nullable=False),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_pseudonym_snapshot', sa.String(length=80), nullable=False),
    sa.Column('reviewer_role_snapshot', sa.String(length=120), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(component = 'R' AND classification = 'required') OR (component = 'P' AND classification = 'preferred') OR (component = 'Q' AND classification IN ('required','preferred'))", name='ck_component_classification'),
    sa.CheckConstraint("NOT critical OR (classification = 'required' AND review_status = 'approved')", name='ck_critical'),
    sa.CheckConstraint("classification IN ('required', 'preferred', 'non_requirement', 'unknown')", name='ck_classification'),
    sa.CheckConstraint("component IN ('R', 'P', 'Q')", name='ck_component'),
    sa.CheckConstraint("operator IN ('SINGLE', 'OR', 'AND')", name='ck_operator'),
    sa.CheckConstraint("review_status IN ('approved', 'pending', 'rejected')", name='ck_review_status'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('matching_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('candidate_profile_id', sa.Uuid(), nullable=True),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('policy_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('input_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('universe_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('pool_limit', sa.Integer(), nullable=False),
    sa.Column('stale_missing_job_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("NOT is_current OR status = 'current'", name='ck_run_current'),
    sa.CheckConstraint("status IN ('current', 'stale', 'historical', 'unreplayable')", name='ck_status'),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['policy_id'], ['scoring_configurations.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_current_matching_run', 'matching_runs', ['candidate_profile_id', 'policy_id'], unique=True, postgresql_where=sa.text('is_current = true'), sqlite_where=sa.text('is_current = 1'))
    op.create_table('candidate_matching_facts',
    sa.Column('candidate_profile_id', sa.Uuid(), nullable=False),
    sa.Column('cv_document_id', sa.Uuid(), nullable=True),
    sa.Column('provenance', sa.String(length=30), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fact_type', sa.String(length=30), nullable=False),
    sa.Column('statement', sa.String(length=1000), nullable=False),
    sa.Column('completion', sa.String(length=20), nullable=False),
    sa.Column('duration_months', sa.Integer(), nullable=True),
    sa.Column('field', sa.String(length=255), nullable=False),
    sa.Column('scope', sa.String(length=500), nullable=False),
    sa.Column('evidence_reference', sa.String(length=255), nullable=False),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_pseudonym_snapshot', sa.String(length=80), nullable=False),
    sa.Column('reviewer_role_snapshot', sa.String(length=120), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("completion IN ('unknown', 'completed', 'in_progress', 'not_completed', 'not_applicable')", name='ck_completion'),
    sa.CheckConstraint("fact_type IN ('occupation', 'qualification', 'experience')", name='ck_fact_type'),
    sa.CheckConstraint("review_status IN ('approved', 'pending', 'rejected')", name='ck_review_status'),
    sa.CheckConstraint('duration_months IS NULL OR duration_months >= 0', name='ck_duration'),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['cv_document_id'], ['cv_documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('job_match_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('job_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('input_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('alignment_fraction', sa.String(length=160), nullable=True),
    sa.Column('alignment_value', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('provisional', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('retrieval_rank', sa.Integer(), nullable=False),
    sa.Column('retrieval_similarity', sa.Numeric(precision=10, scale=6), nullable=False),
    sa.Column('reason_code', sa.String(length=80), nullable=False),
    sa.Column('reason_parameters', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ready', 'provisional', 'stale', 'unreplayable')", name='ck_status'),
    sa.CheckConstraint('(alignment_value IS NULL) = (alignment_fraction IS NULL)', name='ck_alignment_null'),
    sa.CheckConstraint('provisional = (alignment_value IS NULL)', name='ck_provisional_score'),
    sa.CheckConstraint('alignment_value IS NULL OR alignment_value BETWEEN 0 AND 100', name='ck_alignment_range'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['run_id'], ['matching_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'job_id', name='uq_run_job')
    )
    op.create_table('job_occurrence_reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('job_skill_id', sa.Uuid(), nullable=False),
    sa.Column('classification', sa.String(length=30), nullable=False),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_pseudonym_snapshot', sa.String(length=80), nullable=False),
    sa.Column('reviewer_role_snapshot', sa.String(length=120), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("classification IN ('required', 'preferred', 'non_requirement', 'unknown')", name='ck_classification'),
    sa.CheckConstraint("review_status IN ('approved', 'pending', 'rejected')", name='ck_review_status'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_skill_id'], ['job_skills.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_skill_id')
    )
    op.create_table('job_requirement_group_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('job_skill_id', sa.Uuid(), nullable=True),
    sa.Column('job_matching_fact_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint('(job_skill_id IS NOT NULL AND job_matching_fact_id IS NULL) OR (job_skill_id IS NULL AND job_matching_fact_id IS NOT NULL)', name='ck_member_reference'),
    sa.ForeignKeyConstraint(['group_id'], ['job_requirement_groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_matching_fact_id'], ['job_matching_facts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_skill_id'], ['job_skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_group_job_skill', 'job_requirement_group_members', ['job_skill_id'], unique=True, postgresql_where=sa.text('job_skill_id IS NOT NULL'), sqlite_where=sa.text('job_skill_id IS NOT NULL'))
    op.create_index('uq_group_q_fact', 'job_requirement_group_members', ['job_matching_fact_id'], unique=True, postgresql_where=sa.text('job_matching_fact_id IS NOT NULL'), sqlite_where=sa.text('job_matching_fact_id IS NOT NULL'))
    op.create_table('match_score_components',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('result_id', sa.Uuid(), nullable=False),
    sa.Column('component', sa.String(length=1), nullable=False),
    sa.Column('applicability', sa.String(length=20), nullable=False),
    sa.Column('numerator', sa.Numeric(160,0), nullable=True),
    sa.Column('denominator', sa.Numeric(160,0), nullable=True),
    sa.Column('base_weight', sa.Integer(), nullable=False),
    sa.Column('effective_weight_fraction', sa.String(length=160), nullable=True),
    sa.Column('effective_weight_value', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('value_fraction', sa.String(length=160), nullable=True),
    sa.Column('value', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('reason_code', sa.String(length=80), nullable=False),
    sa.Column('reason_parameters', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.CheckConstraint("applicability IN ('applicable', 'not_applicable', 'unknown')", name='ck_applicability'),
    sa.CheckConstraint("component IN ('R', 'P', 'O', 'Q')", name='ck_component'),
    sa.ForeignKeyConstraint(['result_id'], ['job_match_results.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('result_id', 'component', name='uq_result_component')
    )
    op.create_table('skill_gap_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('result_id', sa.Uuid(), nullable=False),
    sa.Column('group_id', sa.Uuid(), nullable=True),
    sa.Column('support_fraction', sa.String(length=160), nullable=True),
    sa.Column('support_value', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('critical', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('evidence_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.Column('reason_code', sa.String(length=80), nullable=False),
    sa.Column('reason_parameters', sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), 'postgresql'), nullable=False),
    sa.CheckConstraint("status IN ('Matched', 'Partially Covered', 'Missing', 'unassessed')", name='ck_status'),
    sa.ForeignKeyConstraint(['group_id'], ['job_requirement_groups.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['result_id'], ['job_match_results.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('result_id', 'group_id', name='uq_result_gap')
    )
    op.execute(sa.text("INSERT INTO scoring_configurations (id, version, canonical_json, policy_hash, engine_version) VALUES (:id, :version, :canonical, :hash, :engine)").bindparams(id=UUID("69e23601-0e59-584a-a502-597fbc9d1667"), version="matching-policy-v1", canonical='{"arithmetic":"exact_rational","component_weights":{"occupation":2,"preferred":3,"qualification_experience":1,"required":7},"critical_aggregation":"maximum_missing_support","critical_penalty_cap":"0.10","dense_numeric_weight":0,"evidence_review_status":"approved","group_operators":["SINGLE","OR","AND"],"nested_groups":false,"policy_version":"matching-policy-v1","readiness":"resolved_applicability_complete_inventory_full_assessment","relationship_allowlist":[],"retrieval":{"primary_pool":20,"template":"e5-job-profile-v2"},"tie_break":["exact_alignment_desc","original_retrieval_rank_asc","lowercase_canonical_job_uuid_asc"],"unknown_requirement_policy":"visible_unscored"}', hash='2a5d9dfb400be9fdea31544e5083f2876fcf685ab41037daa24ef45ce035c8c2', engine="matching-policy-v1"))


    for table in ("candidate_matching_facts", "job_matching_facts"):
        op.add_column(table, sa.Column("taxonomy_concept_id", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("taxonomy_release_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_concept", table, "taxonomy_concepts", ["taxonomy_concept_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key(f"fk_{table}_release", table, "taxonomy_versions", ["taxonomy_release_id"], ["id"], ondelete="SET NULL")
    op.add_column("match_score_components", sa.Column("status", sa.String(20), nullable=False))
    op.create_check_constraint("ck_component_status", "match_score_components", "status IN ('assessed','unassessed','not_applicable')")
    op.create_check_constraint("ck_component_denominator", "match_score_components", "denominator IS NULL OR denominator > 0")
    op.create_table("skill_gap_atomic_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("gap_id", sa.Uuid(), sa.ForeignKey("skill_gap_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("job_requirement_group_members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurrence_fingerprint", sa.String(64), nullable=False),
        sa.Column("support_fraction", sa.String(160), nullable=True),
        sa.Column("support_value", sa.Numeric(10,6), nullable=True),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("reason_parameters", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("gap_id", "member_id", "occurrence_fingerprint", name="uq_gap_atomic_occurrence"),
        sa.CheckConstraint("support_value IS NULL OR support_value BETWEEN 0 AND 1", name="ck_atomic_support"))
    op.add_column("job_occurrence_reviews", sa.Column("reason", sa.String(1000), nullable=False))
    op.create_check_constraint("ck_override_reason", "job_occurrence_reviews", "length(trim(reason)) > 0")
    op.create_unique_constraint("uq_phase6_job_skill_owner", "job_skills", ["id", "job_id"])
    op.create_unique_constraint("uq_group_owner", "job_requirement_groups", ["id", "job_id"])
    op.create_unique_constraint("uq_job_fact_owner", "job_matching_facts", ["id", "job_id"])
    op.add_column("job_requirement_group_members", sa.Column("job_id", sa.Uuid(), nullable=False))
    op.create_foreign_key("fk_member_group_owner", "job_requirement_group_members", "job_requirement_groups",
                          ["group_id","job_id"], ["id","job_id"], ondelete="CASCADE")
    for table, local, target in (("job_requirement_group_members","job_skill_id","job_skills"),
                                 ("job_requirement_group_members","job_matching_fact_id","job_matching_facts"),
                                 ("job_occurrence_reviews","job_skill_id","job_skills")):
        op.create_foreign_key(f"fk_{table}_{local}_owner", table, target, [local,"job_id"], ["id","job_id"], ondelete="CASCADE")
    for table, exact, numeric, name in (
        ("job_match_results","alignment_fraction","alignment_value","alignment"),
        ("match_score_components","value_fraction","value","component"),
        ("match_score_components","effective_weight_fraction","effective_weight_value","weight"),
        ("skill_gap_results","support_fraction","support_value","gap"),
        ("skill_gap_atomic_results","support_fraction","support_value","atomic")):
        op.create_check_constraint(f"ck_{name}_exact", table, f"phase6_fraction_valid({exact}, {numeric})")
        maximum = 100 if name == "alignment" else 1
        op.create_check_constraint(f"ck_{name}_range_exact", table, f"{numeric} IS NULL OR {numeric} BETWEEN 0 AND {maximum}")
    for table in ("candidate_matching_facts", "job_matching_facts", "job_requirement_groups", "job_inventory_reviews", "job_occurrence_reviews", "skill_gap_results"):
        op.create_check_constraint(f"ck_{table}_evidence_bound", table, "length(CAST(evidence_snapshot AS TEXT)) <= 16384")
    for table in ("job_match_results", "match_score_components", "skill_gap_results", "skill_gap_atomic_results"):
        op.create_check_constraint(f"ck_{table}_reason_bound", table, "length(CAST(reason_parameters AS TEXT)) <= 8192")
    op.execute("""
    CREATE FUNCTION phase6_immutable_policy() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Scoring configurations are immutable'; END $$;
    CREATE TRIGGER phase6_policy_immutable BEFORE UPDATE OR DELETE ON scoring_configurations
        FOR EACH ROW EXECUTE FUNCTION phase6_immutable_policy();
    CREATE TRIGGER phase6_policy_no_truncate BEFORE TRUNCATE ON scoring_configurations
        FOR EACH STATEMENT EXECUTE FUNCTION phase6_immutable_policy();
    CREATE FUNCTION phase6_reviewer_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.reviewer_pseudonym_snapshot IS DISTINCT FROM OLD.reviewer_pseudonym_snapshot
         OR NEW.reviewer_role_snapshot IS DISTINCT FROM OLD.reviewer_role_snapshot THEN
        RAISE EXCEPTION 'Reviewer snapshots are immutable';
      END IF;
      RETURN NEW;
    END $$;
    """)
    for table in ("candidate_matching_facts", "job_matching_facts", "job_requirement_groups",
                  "job_inventory_reviews", "job_occurrence_reviews"):
        op.execute(f"CREATE TRIGGER phase6_snapshot_immutable BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION phase6_reviewer_snapshot()")
    op.execute("""
    CREATE FUNCTION phase6_group_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE gid uuid; grp record; n integer;
    BEGIN
      IF TG_TABLE_NAME='job_requirement_group_members' AND TG_OP='UPDATE' THEN
        IF OLD.group_id <> NEW.group_id AND EXISTS (SELECT 1 FROM job_requirement_groups WHERE id=OLD.group_id)
           AND NOT EXISTS (SELECT 1 FROM job_requirement_group_members WHERE group_id=OLD.group_id) THEN
          RAISE EXCEPTION 'Cannot move the final member from an existing group';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'job_requirement_groups' THEN gid := NEW.id;
      ELSIF TG_OP = 'DELETE' THEN gid := OLD.group_id;
      ELSE gid := NEW.group_id; END IF;
      SELECT * INTO grp FROM job_requirement_groups WHERE id = gid;
      IF NOT FOUND THEN RETURN NULL; END IF;
      SELECT count(*) INTO n FROM job_requirement_group_members WHERE group_id = gid;
      IF n = 0 OR (grp.operator = 'SINGLE' AND n <> 1) THEN RAISE EXCEPTION 'Invalid group cardinality'; END IF;
      IF EXISTS (
        SELECT 1 FROM job_requirement_group_members m
        LEFT JOIN job_skills s ON s.id = m.job_skill_id
        LEFT JOIN job_matching_facts f ON f.id = m.job_matching_fact_id
        WHERE m.group_id = gid AND (
          (m.job_skill_id IS NOT NULL AND (s.job_id <> grp.job_id OR s.review_status <> 'approved'
            OR (grp.component = 'Q' AND s.skill_type NOT IN ('qualification','experience'))
            OR (grp.component <> 'Q' AND s.skill_type NOT IN ('skill','tool','domain_knowledge','language'))))
          OR (m.job_matching_fact_id IS NOT NULL AND (f.job_id <> grp.job_id OR f.review_status <> 'approved'
            OR f.fact_type NOT IN ('qualification','experience') OR grp.component <> 'Q'))
        )
      ) THEN RAISE EXCEPTION 'Group membership ownership/type/review mismatch'; END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER phase6_group_check AFTER INSERT OR UPDATE ON job_requirement_groups
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION phase6_group_integrity();
    CREATE CONSTRAINT TRIGGER phase6_member_check AFTER INSERT OR UPDATE OR DELETE ON job_requirement_group_members
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION phase6_group_integrity();
    CREATE FUNCTION phase6_cascade_member_cleanup() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE source_gone boolean;
    BEGIN
      source_gone := (OLD.job_skill_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM job_skills WHERE id=OLD.job_skill_id))
                 OR (OLD.job_matching_fact_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM job_matching_facts WHERE id=OLD.job_matching_fact_id));
      IF source_gone THEN
        IF NOT EXISTS (SELECT 1 FROM job_requirement_group_members WHERE group_id=OLD.group_id) THEN
          DELETE FROM job_requirement_groups WHERE id=OLD.group_id;
        END IF;
        UPDATE job_inventory_reviews SET inventory_complete=false WHERE job_id=OLD.job_id;
        UPDATE job_match_results SET status='stale' WHERE run_id IN (
          SELECT r.id FROM matching_runs r JOIN job_match_results j ON j.run_id=r.id
          WHERE j.job_id=OLD.job_id AND r.is_current AND r.status='current');
        UPDATE matching_runs SET is_current=false,status='stale' WHERE is_current AND status='current'
          AND id IN (SELECT run_id FROM job_match_results WHERE job_id=OLD.job_id);
      END IF;
      RETURN OLD;
    END $$;
    CREATE TRIGGER phase6_member_cascade_cleanup AFTER DELETE ON job_requirement_group_members
      FOR EACH ROW EXECUTE FUNCTION phase6_cascade_member_cleanup();
    CREATE FUNCTION phase6_job_erasure() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      UPDATE matching_runs SET status='unreplayable', is_current=false
        WHERE id IN (SELECT run_id FROM job_match_results WHERE job_id=OLD.id);
      UPDATE skill_gap_results SET evidence_snapshot='{}', reason_parameters='{}'
        WHERE result_id IN (SELECT id FROM job_match_results WHERE job_id=OLD.id);
      UPDATE skill_gap_atomic_results SET reason_parameters='{}'
        WHERE gap_id IN (SELECT id FROM skill_gap_results WHERE result_id IN
          (SELECT id FROM job_match_results WHERE job_id=OLD.id));
      UPDATE match_score_components SET reason_parameters='{}'
        WHERE result_id IN (SELECT id FROM job_match_results WHERE job_id=OLD.id);
      UPDATE job_match_results SET status='unreplayable', reason_parameters='{}' WHERE job_id=OLD.id;
      RETURN OLD;
    END $$;
    CREATE TRIGGER phase6_job_delete BEFORE DELETE ON jobs FOR EACH ROW EXECUTE FUNCTION phase6_job_erasure();
    CREATE FUNCTION phase6_redact_candidate(pid uuid) RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
      UPDATE matching_runs SET status='unreplayable',is_current=false WHERE candidate_profile_id=pid;
      UPDATE skill_gap_atomic_results SET reason_parameters='{}' WHERE gap_id IN (
        SELECT g.id FROM skill_gap_results g JOIN job_match_results j ON j.id=g.result_id
        JOIN matching_runs r ON r.id=j.run_id WHERE r.candidate_profile_id=pid);
      UPDATE skill_gap_results SET evidence_snapshot='{}',reason_parameters='{}' WHERE result_id IN (
        SELECT j.id FROM job_match_results j JOIN matching_runs r ON r.id=j.run_id WHERE r.candidate_profile_id=pid);
      UPDATE match_score_components SET reason_parameters='{}' WHERE result_id IN (
        SELECT j.id FROM job_match_results j JOIN matching_runs r ON r.id=j.run_id WHERE r.candidate_profile_id=pid);
      UPDATE job_match_results SET status='unreplayable',reason_parameters='{}'
        WHERE run_id IN (SELECT id FROM matching_runs WHERE candidate_profile_id=pid);
    END $$;
    CREATE FUNCTION phase6_candidate_erasure() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='candidate_profiles' THEN PERFORM phase6_redact_candidate(OLD.id);
      ELSE PERFORM phase6_redact_candidate(OLD.candidate_profile_id); END IF;
      RETURN OLD;
    END $$;
    CREATE TRIGGER phase6_profile_delete BEFORE DELETE ON candidate_profiles FOR EACH ROW EXECUTE FUNCTION phase6_candidate_erasure();
    CREATE TRIGGER phase6_cv_delete BEFORE DELETE ON cv_documents FOR EACH ROW EXECUTE FUNCTION phase6_candidate_erasure();
    CREATE TRIGGER phase6_fact_delete BEFORE DELETE ON candidate_matching_facts FOR EACH ROW EXECUTE FUNCTION phase6_candidate_erasure();
    """)


def downgrade():
    op.execute("DROP TRIGGER phase6_job_delete ON jobs")
    op.execute("DROP TRIGGER phase6_profile_delete ON candidate_profiles")
    op.execute("DROP TRIGGER phase6_cv_delete ON cv_documents")
    op.drop_table("skill_gap_atomic_results")
    op.drop_table("skill_gap_results")
    op.drop_table("match_score_components")
    op.drop_table("job_requirement_group_members")
    op.drop_table("job_occurrence_reviews")
    op.drop_table("job_match_results")
    op.drop_table("candidate_matching_facts")
    op.drop_table("matching_runs")
    op.drop_table("job_requirement_groups")
    op.drop_table("job_matching_facts")
    op.drop_table("job_inventory_reviews")
    op.drop_table("scoring_configurations")
    op.drop_constraint("uq_phase6_job_skill_owner", "job_skills", type_="unique")
    for function in ("phase6_job_erasure", "phase6_group_integrity", "phase6_cascade_member_cleanup",
                     "phase6_reviewer_snapshot", "phase6_immutable_policy", "phase6_policy_insert", "phase6_candidate_erasure"):
        op.execute(f"DROP FUNCTION {function}()")
    op.execute("DROP FUNCTION phase6_redact_candidate(uuid)")
    op.execute("DROP FUNCTION phase6_fraction_valid(text,numeric)")

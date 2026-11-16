"""Source-bound manual inventory capabilities, isolated from retrieval inputs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_manual_job_capabilities"
down_revision = "0010_matching_input_integrity"
branch_labels = None
depends_on = None


def upgrade():
    columns = [sa.Column("id", sa.Uuid(), primary_key=True),
               sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)]
    for name, size in (("raw_text", 255), ("normalized_text", 512), ("skill_type", 30),
                       ("compatibility_family", 30), ("classification", 30), ("provenance", 30),
                       ("cleaned_description_sha256", 64), ("evidence_sentence", 1000),
                       ("review_reason", 1000), ("ledger_reference", 255), ("review_status", 20),
                       ("reviewer_pseudonym_snapshot", 80), ("reviewer_role_snapshot", 120)):
        columns.append(sa.Column(name, sa.String(size), nullable=False))
    for name in ("capability_start", "capability_end", "evidence_start", "evidence_end"):
        columns.append(sa.Column(name, sa.Integer(), nullable=False))
    columns += [sa.Column("no_local_file_anchor", sa.Boolean(), nullable=False),
                sa.Column("local_source_sha256", sa.String(64)),
                *[sa.Column(name, sa.Integer()) for name in ("local_line_start", "local_line_end", "local_start", "local_end")],
                sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
                sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
                sa.UniqueConstraint("id", "job_id", name="uq_manual_owner"),
                sa.UniqueConstraint("job_id", "compatibility_family", "normalized_text", name="uq_manual_key")]
    op.create_table("job_manual_capabilities", *columns)
    checks = {
        "approved": "review_status = 'approved' AND provenance = 'manual_transcription'",
        "classification": "classification IN ('required','preferred')",
        "family": "(skill_type IN ('skill','tool') AND compatibility_family = 'technical_capability') OR (skill_type IN ('domain_knowledge','language') AND compatibility_family = skill_type)",
        "spans": "0 <= evidence_start AND evidence_start <= capability_start AND capability_start < capability_end AND capability_end <= evidence_end",
        "lengths": "length(raw_text) BETWEEN 1 AND 255 AND length(normalized_text) BETWEEN 1 AND 512 AND length(evidence_sentence) BETWEEN 1 AND 1000 AND length(review_reason) BETWEEN 1 AND 1000 AND length(ledger_reference) BETWEEN 1 AND 255",
        "hashes": "cleaned_description_sha256 ~ '^[0-9a-f]{64}$' AND (local_source_sha256 IS NULL OR local_source_sha256 ~ '^[0-9a-f]{64}$')",
        "local_anchor": "(local_source_sha256 IS NULL AND local_line_start IS NULL AND local_line_end IS NULL AND local_start IS NULL AND local_end IS NULL) OR (local_source_sha256 IS NOT NULL AND local_line_start IS NOT NULL AND local_line_end IS NOT NULL AND local_start IS NOT NULL AND local_end IS NOT NULL AND local_line_start >= 1 AND local_line_end >= local_line_start AND local_start >= 0 AND local_end > local_start)",
        "snapshot_bound": "octet_length(evidence_snapshot::text) <= 8192",
        "no_local_file": "no_local_file_anchor = (local_source_sha256 IS NULL)",
    }
    for name, expression in checks.items():
        op.create_check_constraint("ck_manual_" + name, "job_manual_capabilities", expression)
    op.create_index("ix_job_manual_capabilities_job_id", "job_manual_capabilities", ["job_id"])
    op.add_column("job_requirement_group_members", sa.Column("manual_capability_id", sa.Uuid()))
    op.drop_constraint("ck_member_reference", "job_requirement_group_members", type_="check")
    op.create_check_constraint("ck_member_reference", "job_requirement_group_members",
        "num_nonnulls(job_skill_id, job_matching_fact_id, manual_capability_id) = 1")
    op.create_foreign_key("fk_member_manual_owner", "job_requirement_group_members", "job_manual_capabilities",
        ["manual_capability_id", "job_id"], ["id", "job_id"], deferrable=True, initially="DEFERRED")
    op.create_index("uq_group_manual", "job_requirement_group_members", ["manual_capability_id"],
        unique=True, postgresql_where=sa.text("manual_capability_id IS NOT NULL"))
    for table in ("job_inventory_reviews", "matching_runs"):
        op.add_column(table, sa.Column("input_adapter_version", sa.String(80)))
    op.execute("""
    CREATE FUNCTION phase6_manual_source() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE source text;
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'reviewed_by' - 'updated_at') IS DISTINCT FROM
           (to_jsonb(OLD) - 'reviewed_by' - 'updated_at') OR
           (NEW.reviewed_by IS DISTINCT FROM OLD.reviewed_by AND
             NOT (NEW.reviewed_by IS NULL AND NOT EXISTS (SELECT 1 FROM users WHERE id=OLD.reviewed_by))) THEN
          RAISE EXCEPTION 'Manual capability provenance/content is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      SELECT cleaned_description INTO source FROM jobs WHERE id=NEW.job_id;
      IF source IS NULL OR NEW.cleaned_description_sha256 <> encode(sha256(convert_to(source,'UTF8')),'hex')
         OR NEW.evidence_end > char_length(source)
         OR NEW.raw_text <> substring(source FROM NEW.capability_start+1 FOR NEW.capability_end-NEW.capability_start)
         OR NEW.evidence_sentence <> substring(source FROM NEW.evidence_start+1 FOR NEW.evidence_end-NEW.evidence_start) THEN
        RAISE EXCEPTION 'Manual capability source/hash/span mismatch' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER phase6_manual_source BEFORE INSERT OR UPDATE ON job_manual_capabilities
      FOR EACH ROW EXECUTE FUNCTION phase6_manual_source();
    CREATE TRIGGER phase6_input_gate BEFORE INSERT OR UPDATE OR DELETE ON job_manual_capabilities
      FOR EACH STATEMENT EXECUTE FUNCTION phase6_input_gate();
    CREATE TRIGGER phase6_input_invalidate AFTER INSERT OR UPDATE OR DELETE ON job_manual_capabilities
      FOR EACH ROW EXECUTE FUNCTION phase6_invalidate_inputs('job');

    CREATE FUNCTION phase6_manual_group_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE gid uuid;
    BEGIN
      IF TG_TABLE_NAME='job_requirement_groups' THEN gid := NEW.id;
      ELSIF TG_OP='DELETE' THEN gid := OLD.group_id;
      ELSE gid := NEW.group_id; END IF;
      IF EXISTS (SELECT 1 FROM job_requirement_groups g
        JOIN job_requirement_group_members m ON m.group_id=g.id
        LEFT JOIN job_manual_capabilities c ON c.id=m.manual_capability_id
        WHERE g.id=gid AND m.manual_capability_id IS NOT NULL AND
          (c.id IS NULL OR c.job_id<>g.job_id OR c.review_status<>'approved' OR g.component NOT IN ('R','P')
            OR c.classification<>g.classification OR
            (g.critical AND coalesce(length(trim(g.evidence_snapshot->>'critical_source_rationale')),0)=0))) THEN
        RAISE EXCEPTION 'Manual group ownership/classification/rationale mismatch' USING ERRCODE='23514';
      END IF;
      RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER phase6_manual_group_check AFTER INSERT OR UPDATE ON job_requirement_groups
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION phase6_manual_group_integrity();
    CREATE CONSTRAINT TRIGGER phase6_manual_member_check AFTER INSERT OR UPDATE OR DELETE ON job_requirement_group_members
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION phase6_manual_group_integrity();

    CREATE FUNCTION phase6_adapter_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (TG_OP='INSERT' AND (NEW.input_adapter_version IS NULL OR length(trim(NEW.input_adapter_version))=0))
        OR (TG_OP='UPDATE' AND NEW.input_adapter_version IS DISTINCT FROM OLD.input_adapter_version) THEN
        RAISE EXCEPTION 'Explicit immutable input adapter version required' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    """)
    for table in ("job_inventory_reviews", "matching_runs"):
        op.execute(f"CREATE TRIGGER phase6_adapter_version BEFORE INSERT OR UPDATE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION phase6_adapter_version()")


def downgrade():
    # Guard first. Even version tags without manual rows bind the new contract.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM job_manual_capabilities) OR
         EXISTS (SELECT 1 FROM job_requirement_group_members WHERE manual_capability_id IS NOT NULL) OR
         EXISTS (SELECT 1 FROM job_inventory_reviews WHERE input_adapter_version IS NOT NULL) OR
         EXISTS (SELECT 1 FROM matching_runs WHERE input_adapter_version IS NOT NULL) OR
         EXISTS (SELECT 1 FROM skill_gap_atomic_results WHERE reason_parameters::text LIKE '%phase6_manual_capability%') OR
         EXISTS (SELECT 1 FROM skill_gap_results WHERE evidence_snapshot::text LIKE '%phase6_manual_capability%') THEN
        RAISE EXCEPTION 'Downgrade refuses manual-capability or adapter-dependent history';
      END IF;
    END $$""")
    for table in ("job_inventory_reviews", "matching_runs"):
        op.execute(f"DROP TRIGGER phase6_adapter_version ON {table}")
        op.drop_column(table, "input_adapter_version")
    op.execute("DROP FUNCTION phase6_adapter_version()")
    op.execute("DROP TRIGGER phase6_manual_group_check ON job_requirement_groups")
    op.execute("DROP TRIGGER phase6_manual_member_check ON job_requirement_group_members")
    op.execute("DROP FUNCTION phase6_manual_group_integrity()")
    op.drop_index("uq_group_manual", table_name="job_requirement_group_members")
    op.drop_constraint("fk_member_manual_owner", "job_requirement_group_members", type_="foreignkey")
    op.drop_constraint("ck_member_reference", "job_requirement_group_members", type_="check")
    op.drop_column("job_requirement_group_members", "manual_capability_id")
    op.create_check_constraint("ck_member_reference", "job_requirement_group_members",
        "(job_skill_id IS NOT NULL AND job_matching_fact_id IS NULL) OR (job_skill_id IS NULL AND job_matching_fact_id IS NOT NULL)")
    op.drop_table("job_manual_capabilities")
    op.execute("DROP FUNCTION phase6_manual_source()")

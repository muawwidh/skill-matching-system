"""Live job sources; drop the unused candidate_job_matches table (D049, D052).

Revision ID: 0009_live_jobs
Revises: 0008_dense_retrieval

`jobs.source` already exists (default "manual"); every existing job keeps
"manual". Evaluation jobs are tagged afterwards with
`python -m app.jobs.cli mark-evaluation-jobs --mapping <file>`, because their
identity lives only in the private evaluation mapping, which a migration must
not read.

Downgrade recreates `candidate_job_matches` empty; its rows (not written since
D049) are not restored.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_live_jobs"
down_revision = "0008_dense_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("jobs", sa.Column("external_url", sa.String(1000), server_default="", nullable=False))
    op.add_column("jobs", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("content_hash", sa.String(64), server_default="", nullable=False))
    op.execute("UPDATE jobs SET source = 'manual' WHERE source IS NULL OR source = ''")
    # NULL external IDs (manual and evaluation jobs) never conflict.
    op.create_unique_constraint("uq_jobs_source_external_id", "jobs", ["source", "external_id"])
    op.create_index("ix_jobs_source_status", "jobs", ["source", "status"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])

    op.drop_index("ix_candidate_job_matches_candidate_score", table_name="candidate_job_matches")
    op.drop_table("candidate_job_matches")


def downgrade() -> None:
    op.create_table(
        "candidate_job_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_profile_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("matched_required", sa.JSON(), nullable=False),
        sa.Column("matched_preferred", sa.JSON(), nullable=False),
        sa.Column("missing_required", sa.JSON(), nullable=False),
        sa.Column("missing_preferred", sa.JSON(), nullable=False),
        sa.Column("candidate_skill_count", sa.Integer(), nullable=False),
        sa.Column("job_skill_count", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_profile_id", "job_id", name="uq_candidate_job_match"),
    )
    op.create_index("ix_candidate_job_matches_candidate_score", "candidate_job_matches",
                    ["candidate_profile_id", "score"])

    op.drop_index("ix_jobs_content_hash", table_name="jobs")
    op.drop_index("ix_jobs_source_status", table_name="jobs")
    op.drop_constraint("uq_jobs_source_external_id", "jobs", type_="unique")
    # Live and evaluation jobs become manual again; their external identity is dropped.
    op.execute("UPDATE jobs SET source = 'manual' WHERE source <> 'manual'")
    for column in ("content_hash", "last_seen_at", "posted_at", "external_url", "external_id"):
        op.drop_column("jobs", column)

"""candidate job matching tables

Revision ID: 0004_candidate_job_matching
Revises: 0003_skill_extraction
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_candidate_job_matching"
down_revision = "0003_skill_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index(
        "ix_candidate_job_matches_candidate_score",
        "candidate_job_matches",
        ["candidate_profile_id", "score"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_job_matches_candidate_score", table_name="candidate_job_matches")
    op.drop_table("candidate_job_matches")

"""Candidate work entries for relevant experience (D060).

Revision ID: 0010_candidate_work_entries
Revises: 0009_live_jobs

Self-entered work history: job title, start month, end month (NULL =
present) and the chosen ESCO occupation. No employer column by design.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_candidate_work_entries"
down_revision = "0009_live_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_work_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_profile_id", sa.Uuid(),
                  sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=True),
        sa.Column("occupation_concept_id", sa.Uuid(),
                  sa.ForeignKey("taxonomy_concepts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_month IS NULL OR end_month >= start_month", name="ck_work_entry_period"),
    )
    op.create_index("ix_candidate_work_entries_profile", "candidate_work_entries", ["candidate_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_work_entries_profile", table_name="candidate_work_entries")
    op.drop_table("candidate_work_entries")

"""Candidate preferences: the related-experience filter switch (D060).

Revision ID: 0011_candidate_preferences
Revises: 0010_candidate_work_entries

One row per candidate who changed a setting; no row means the defaults
(filter off). A separate table keeps existing profile rows unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_candidate_preferences"
down_revision = "0010_candidate_work_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_preferences",
        sa.Column("candidate_profile_id", sa.Uuid(),
                  sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hide_below_experience", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candidate_preferences")

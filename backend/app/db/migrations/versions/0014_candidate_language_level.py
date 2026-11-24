"""Optional proficiency level for languages a candidate adds by hand.

Revision ID: 0014_candidate_language_level
Revises: 0013_work_entry_source_cv

`proficiency_level` (A1-C2 or "native") is set only on language skills the
candidate adds on My profile; every other skill keeps NULL. It is shown to the
candidate and never compared or used for matching.
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_candidate_language_level"
down_revision = "0013_work_entry_source_cv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidate_skills", sa.Column("proficiency_level", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_skills", "proficiency_level")

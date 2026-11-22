"""Work entries remember the CV they were pre-filled from.

Revision ID: 0013_work_entry_source_cv
Revises: 0012_occupation_label_embeddings

`source_cv_id` is set only for entries the candidate added from a CV
suggestion; manual entries keep NULL. Deleting a CV lets the candidate also
remove the entries taken from it; entries that are kept lose the link
(SET NULL). Existing rows stay NULL: their source CV was not recorded.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_work_entry_source_cv"
down_revision = "0012_occupation_label_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidate_work_entries", sa.Column("source_cv_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_candidate_work_entries_source_cv", "candidate_work_entries", "cv_documents",
                          ["source_cv_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_candidate_work_entries_source_cv", "candidate_work_entries", ["source_cv_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_work_entries_source_cv", table_name="candidate_work_entries")
    op.drop_constraint("fk_candidate_work_entries_source_cv", "candidate_work_entries", type_="foreignkey")
    op.drop_column("candidate_work_entries", "source_cv_id")

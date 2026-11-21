"""Occupation label embeddings for work-entry suggestions (D060).

Revision ID: 0012_occupation_label_embeddings
Revises: 0011_candidate_preferences

E5 "passage:" embeddings of ESCO occupation preferred and alternative labels,
filled once by `python -m app.retrieval.cli embed-occupation-labels`. Used only
to add nearest-neighbour suggestions in the candidate's work-entry form.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0012_occupation_label_embeddings"
down_revision = "0011_candidate_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "occupation_label_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("concept_id", sa.Uuid(), sa.ForeignKey("taxonomy_concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("model_revision", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("concept_id", "label", "model_id", "model_revision", name="uq_occupation_label_embedding"),
    )
    op.create_index("ix_occupation_label_embeddings_concept_id", "occupation_label_embeddings", ["concept_id"])


def downgrade() -> None:
    op.drop_index("ix_occupation_label_embeddings_concept_id", table_name="occupation_label_embeddings")
    op.drop_table("occupation_label_embeddings")

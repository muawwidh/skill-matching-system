"""Release-independent candidate/profile and job vector indexes."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0008_dense_retrieval"
down_revision = "0007_taxonomy_review_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for name, owner in (("candidate_profile_embeddings", "candidate_profile_id"), ("job_embeddings", "job_id")):
        target = "candidate_profiles" if owner == "candidate_profile_id" else "jobs"
        op.create_table(
            name,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(owner, sa.Uuid(), sa.ForeignKey(f"{target}.id", ondelete="CASCADE"), nullable=False),
            sa.Column("embedding", Vector(384), nullable=False),
            sa.Column("model_id", sa.String(160), nullable=False),
            sa.Column("model_revision", sa.String(64), nullable=False),
            sa.Column("template_version", sa.String(40), nullable=False),
            sa.Column("source_hash", sa.String(64), nullable=False),
            sa.Column("taxonomy_fingerprint", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("status in ('ready', 'stale', 'failed')", name=f"ck_{'profile' if owner == 'candidate_profile_id' else 'job'}_embedding_status"),
            sa.UniqueConstraint(owner, "model_id", "model_revision", "template_version", name=f"uq_{'profile' if owner == 'candidate_profile_id' else 'job'}_embedding_identity"),
        )
        op.create_index(f"ix_{name}_{owner}", name, [owner])


def downgrade() -> None:
    for name, owner in (("job_embeddings", "job_id"), ("candidate_profile_embeddings", "candidate_profile_id")):
        op.drop_index(f"ix_{name}_{owner}", table_name=name)
        op.drop_table(name)
    # Keep vector installed: another database object or integration may use it.

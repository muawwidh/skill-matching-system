"""Append-only application review history; no existing decision/data repairs."""
from alembic import op
import sqlalchemy as sa

revision = "0007_taxonomy_review_audit"
down_revision = "0006_official_taxonomy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("term_source", sa.String(40), nullable=False),
        sa.Column("extracted_term_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=False),
        sa.Column("after_state", sa.JSON(), nullable=False),
    )
    op.create_index("ix_taxonomy_review_event_term", "taxonomy_review_events",
                    ["term_source", "extracted_term_id", "created_at"])


def downgrade() -> None:
    op.drop_table("taxonomy_review_events")

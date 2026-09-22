"""taxonomy integration tables

Revision ID: 0005_taxonomy_integration
Revises: 0004_candidate_job_matching
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_taxonomy_integration"
down_revision = "0004_candidate_job_matching"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "taxonomy_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("homepage_url", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_taxonomy_sources_code", "taxonomy_sources", ["code"], unique=True)

    op.create_table(
        "taxonomy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("release_date", sa.String(40), nullable=False),
        sa.Column("import_filename", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["source_id"], ["taxonomy_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version", name="uq_taxonomy_source_version"),
    )

    op.create_table(
        "taxonomy_concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("preferred_label", sa.String(500), nullable=False),
        sa.Column("normalized_label", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("concept_type", sa.String(80), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["taxonomy_version_id"], ["taxonomy_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_version_id", "external_id", name="uq_taxonomy_concept_external"),
    )
    op.create_index("ix_taxonomy_concepts_preferred_label", "taxonomy_concepts", ["preferred_label"])
    op.create_index("ix_taxonomy_concepts_normalized_label", "taxonomy_concepts", ["normalized_label"])
    op.create_index("ix_taxonomy_concepts_concept_type", "taxonomy_concepts", ["concept_type"])

    op.create_table(
        "taxonomy_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("normalized_label", sa.String(500), nullable=False),
        sa.Column("label_type", sa.String(40), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "normalized_label", "label_type", name="uq_taxonomy_label"),
    )
    op.create_index("ix_taxonomy_labels_normalized_label", "taxonomy_labels", ["normalized_label"])

    op.create_table(
        "taxonomy_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_concept_id", sa.Uuid(), nullable=False),
        sa.Column("target_concept_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(80), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["source_concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_concept_id", "target_concept_id", "relationship_type", name="uq_taxonomy_relationship"),
    )

    op.create_table(
        "occupations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("job_zone", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["taxonomy_version_id"], ["taxonomy_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["taxonomy_concepts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_version_id", "code", name="uq_occupation_code"),
    )
    op.create_index("ix_occupations_code", "occupations", ["code"])

    op.create_table(
        "esco_onet_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("esco_concept_id", sa.Uuid(), nullable=False),
        sa.Column("onet_occupation_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_type", sa.String(80), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["esco_concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["onet_occupation_id"], ["occupations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("esco_concept_id", "onet_occupation_id", name="uq_esco_onet_mapping"),
    )

    op.create_table(
        "taxonomy_link_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("term_source", sa.String(40), nullable=False),
        sa.Column("extracted_term_id", sa.Uuid(), nullable=False),
        sa.Column("raw_text", sa.String(500), nullable=False),
        sa.Column("normalized_text", sa.String(500), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("match_method", sa.String(80), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_source", "extracted_term_id", "concept_id", name="uq_taxonomy_link_candidate"),
    )
    op.create_index("ix_taxonomy_link_candidates_term_source", "taxonomy_link_candidates", ["term_source"])
    op.create_index("ix_taxonomy_link_candidates_extracted_term_id", "taxonomy_link_candidates", ["extracted_term_id"])

    op.create_table(
        "approved_taxonomy_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("term_source", sa.String(40), nullable=False),
        sa.Column("extracted_term_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("link_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("match_method", sa.String(80), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("approval_source", sa.String(40), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["concept_id"], ["taxonomy_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["link_candidate_id"], ["taxonomy_link_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_source", "extracted_term_id", name="uq_approved_taxonomy_term"),
    )
    op.create_index("ix_approved_taxonomy_links_term_source", "approved_taxonomy_links", ["term_source"])
    op.create_index("ix_approved_taxonomy_links_extracted_term_id", "approved_taxonomy_links", ["extracted_term_id"])


def downgrade() -> None:
    op.drop_table("approved_taxonomy_links")
    op.drop_table("taxonomy_link_candidates")
    op.drop_table("esco_onet_mappings")
    op.drop_table("occupations")
    op.drop_table("taxonomy_relationships")
    op.drop_table("taxonomy_labels")
    op.drop_table("taxonomy_concepts")
    op.drop_table("taxonomy_versions")
    op.drop_table("taxonomy_sources")

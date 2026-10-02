"""Release-scoped relationships and lossless structured O*NET records."""
from alembic import op
import sqlalchemy as sa

revision = "0006_official_taxonomy"
down_revision = "0005_taxonomy_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("taxonomy_versions", sa.Column("import_report", sa.JSON(), nullable=False, server_default="{}"))
    op.create_unique_constraint("uq_concept_id_version", "taxonomy_concepts", ["id", "taxonomy_version_id"])
    op.add_column("taxonomy_relationships", sa.Column("taxonomy_version_id", sa.Uuid(), nullable=True))
    op.add_column("taxonomy_relationships", sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"))
    op.execute("""UPDATE taxonomy_relationships SET taxonomy_version_id = c.taxonomy_version_id
                  FROM taxonomy_concepts c WHERE c.id = source_concept_id""")
    op.alter_column("taxonomy_relationships", "taxonomy_version_id", nullable=False)
    op.create_foreign_key("fk_relationship_version", "taxonomy_relationships", "taxonomy_versions",
                          ["taxonomy_version_id"], ["id"], ondelete="CASCADE")
    for endpoint in ("source", "target"):
        op.create_foreign_key(f"fk_relationship_{endpoint}_version", "taxonomy_relationships", "taxonomy_concepts",
                             [f"{endpoint}_concept_id", "taxonomy_version_id"], ["id", "taxonomy_version_id"], ondelete="CASCADE")
    op.create_table(
        "onet_data_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("taxonomy_version_id", sa.Uuid(), sa.ForeignKey("taxonomy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset", sa.String(120), nullable=False),
        sa.Column("record_key", sa.String(64), nullable=False),
        sa.Column("occupation_code", sa.String(100), nullable=True),
        sa.Column("element_id", sa.String(40), nullable=False),
        sa.Column("scale_id", sa.String(20), nullable=False),
        sa.Column("task_id", sa.String(40), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("numeric_value", sa.Numeric(), nullable=True),
        sa.Column("source_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("taxonomy_version_id", "dataset", "record_key", name="uq_onet_record"),
        sa.ForeignKeyConstraint(["taxonomy_version_id", "occupation_code"], ["occupations.taxonomy_version_id", "occupations.code"],
                                name="fk_onet_record_occupation", ondelete="CASCADE"),
    )
    for column in ("taxonomy_version_id", "dataset", "occupation_code"):
        op.create_index(f"ix_onet_data_records_{column}", "onet_data_records", [column])


def downgrade() -> None:
    op.drop_table("onet_data_records")
    for name in ("fk_relationship_source_version", "fk_relationship_target_version", "fk_relationship_version"):
        op.drop_constraint(name, "taxonomy_relationships", type_="foreignkey")
    op.drop_column("taxonomy_relationships", "metadata_json")
    op.drop_column("taxonomy_relationships", "taxonomy_version_id")
    op.drop_constraint("uq_concept_id_version", "taxonomy_concepts", type_="unique")
    op.drop_column("taxonomy_versions", "import_report")

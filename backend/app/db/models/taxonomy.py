from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


JsonColumn = JSON().with_variant(JSONB, "postgresql")


class TaxonomySource(TimestampMixin, Base):
    __tablename__ = "taxonomy_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


class TaxonomyVersion(TimestampMixin, Base):
    __tablename__ = "taxonomy_versions"
    __table_args__ = (UniqueConstraint("source_id", "version", name="uq_taxonomy_source_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("taxonomy_sources.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    release_date: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    import_filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source: Mapped[TaxonomySource] = relationship(lazy="selectin")


class TaxonomyConcept(TimestampMixin, Base):
    __tablename__ = "taxonomy_concepts"
    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "external_id", name="uq_taxonomy_concept_external"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    taxonomy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    preferred_label: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_label: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    concept_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonColumn, default=dict, nullable=False)

    taxonomy_version: Mapped[TaxonomyVersion] = relationship(lazy="selectin")
    labels: Mapped[list["TaxonomyLabel"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan", lazy="selectin"
    )


class TaxonomyLabel(TimestampMixin, Base):
    __tablename__ = "taxonomy_labels"
    __table_args__ = (
        UniqueConstraint("concept_id", "normalized_label", "label_type", name="uq_taxonomy_label"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("taxonomy_concepts.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    label_type: Mapped[str] = mapped_column(String(40), default="alternative", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)

    concept: Mapped[TaxonomyConcept] = relationship(back_populates="labels")


class TaxonomyRelationship(TimestampMixin, Base):
    __tablename__ = "taxonomy_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_concept_id", "target_concept_id", "relationship_type",
            name="uq_taxonomy_relationship",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="CASCADE")
    )
    target_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="CASCADE")
    )
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)


class Occupation(TimestampMixin, Base):
    __tablename__ = "occupations"
    __table_args__ = (UniqueConstraint("taxonomy_version_id", "code", name="uq_occupation_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    taxonomy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_versions.id", ondelete="CASCADE")
    )
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    job_zone: Mapped[int] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JsonColumn, default=dict, nullable=False)

    taxonomy_version: Mapped[TaxonomyVersion] = relationship(lazy="selectin")
    concept: Mapped[TaxonomyConcept] = relationship(lazy="selectin")


class EscoOnetMapping(TimestampMixin, Base):
    __tablename__ = "esco_onet_mappings"
    __table_args__ = (
        UniqueConstraint("esco_concept_id", "onet_occupation_id", name="uq_esco_onet_mapping"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    esco_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="CASCADE")
    )
    onet_occupation_id: Mapped[UUID] = mapped_column(
        ForeignKey("occupations.id", ondelete="CASCADE")
    )
    mapping_type: Mapped[str] = mapped_column(String(80), default="related", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    version: Mapped[str] = mapped_column(String(100), default="", nullable=False)

    esco_concept: Mapped[TaxonomyConcept] = relationship(lazy="selectin")
    onet_occupation: Mapped[Occupation] = relationship(lazy="selectin")


class TaxonomyLinkCandidate(TimestampMixin, Base):
    __tablename__ = "taxonomy_link_candidates"
    __table_args__ = (
        UniqueConstraint(
            "term_source", "extracted_term_id", "concept_id", name="uq_taxonomy_link_candidate"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    term_source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    extracted_term_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(500), nullable=False)
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="CASCADE")
    )
    match_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    reviewed_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    concept: Mapped[TaxonomyConcept] = relationship(lazy="selectin")


class ApprovedTaxonomyLink(TimestampMixin, Base):
    __tablename__ = "approved_taxonomy_links"
    __table_args__ = (
        UniqueConstraint("term_source", "extracted_term_id", name="uq_approved_taxonomy_term"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    term_source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    extracted_term_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="CASCADE")
    )
    link_candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_link_candidates.id", ondelete="SET NULL"), nullable=True
    )
    match_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    approval_source: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    concept: Mapped[TaxonomyConcept] = relationship(lazy="selectin")

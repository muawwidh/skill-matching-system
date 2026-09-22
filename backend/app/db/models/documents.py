from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


JsonColumn = JSON().with_variant(JSONB, "postgresql")


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    headline: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    consent_to_process_cv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False)

    cv_documents: Mapped[list["CvDocument"]] = relationship(
        back_populates="candidate_profile",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CvDocument(TimestampMixin, Base):
    __tablename__ = "cv_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="cv_documents")
    sections: Mapped[list["CvSection"]] = relationship(
        back_populates="cv_document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CvSection(TimestampMixin, Base):
    __tablename__ = "cv_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cv_document_id: Mapped[UUID] = mapped_column(ForeignKey("cv_documents.id", ondelete="CASCADE"))
    section_type: Mapped[str] = mapped_column(String(80), nullable=False)
    heading: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), default="heading_rules", nullable=False)

    cv_document: Mapped[CvDocument] = relationship(back_populates="sections")


class ExtractedCandidateTerm(TimestampMixin, Base):
    __tablename__ = "extracted_candidate_terms"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cv_document_id: Mapped[UUID] = mapped_column(ForeignKey("cv_documents.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    term_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_section: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    evidence_sentence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    cv_document: Mapped[CvDocument] = relationship(lazy="selectin")


class CandidateSkill(TimestampMixin, Base):
    __tablename__ = "candidate_skills"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    extracted_term_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_candidate_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(80), default="skill", nullable=False)
    evidence_sentence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="extraction", nullable=False)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    employment_type: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    sections: Mapped[list["JobSection"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class JobSection(TimestampMixin, Base):
    __tablename__ = "job_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    section_type: Mapped[str] = mapped_column(String(80), nullable=False)
    heading: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), default="heading_rules", nullable=False)

    job: Mapped[Job] = relationship(back_populates="sections")


class ExtractedJobTerm(TimestampMixin, Base):
    __tablename__ = "extracted_job_terms"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    term_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_section: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    evidence_sentence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    job: Mapped[Job] = relationship(lazy="selectin")


class JobSkill(TimestampMixin, Base):
    __tablename__ = "job_skills"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    extracted_term_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_job_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(80), default="skill", nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    evidence_sentence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="extraction", nullable=False)


class CandidateJobMatch(TimestampMixin, Base):
    __tablename__ = "candidate_job_matches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    matched_required: Mapped[list] = mapped_column(JsonColumn, default=list, nullable=False)
    matched_preferred: Mapped[list] = mapped_column(JsonColumn, default=list, nullable=False)
    missing_required: Mapped[list] = mapped_column(JsonColumn, default=list, nullable=False)
    missing_preferred: Mapped[list] = mapped_column(JsonColumn, default=list, nullable=False)
    candidate_skill_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    job_skill_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    candidate_profile: Mapped[CandidateProfile] = relationship(lazy="selectin")
    job: Mapped[Job] = relationship(lazy="selectin")


class ProcessingLog(TimestampMixin, Base):
    __tablename__ = "processing_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonColumn, default=dict, nullable=False)

"""Candidate work entries for relevant experience (DECISIONS.md D060). No employer is stored."""
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CandidateWorkEntry(TimestampMixin, Base):
    __tablename__ = "candidate_work_entries"
    __table_args__ = (
        CheckConstraint("end_month IS NULL OR end_month >= start_month", name="ck_work_entry_period"),
        Index("ix_candidate_work_entries_profile", "candidate_profile_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # First day of the month; end_month NULL means "present".
    start_month: Mapped[date] = mapped_column(Date, nullable=False)
    end_month: Mapped[date] = mapped_column(Date, nullable=True)
    # The ESCO occupation the candidate chose, or none.
    occupation_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("taxonomy_concepts.id", ondelete="SET NULL"), nullable=True)
    # "manual" (typed) or "cv_detected" (pre-filled from a CV and confirmed by the candidate).
    source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)

    occupation = relationship("TaxonomyConcept", lazy="joined")

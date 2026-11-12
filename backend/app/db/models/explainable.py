"""Relational Phase 6 storage, separate from the legacy match prototype."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.documents import JsonColumn


def enum_check(column: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(f"{column} IN {values!r}", name=f"ck_{column}")


REVIEW = ("approved", "pending", "rejected")
CLASSIFICATION = ("required", "preferred", "non_requirement", "unknown")
APPLICABILITY = ("applicable", "not_applicable", "unknown")


class ScoringConfiguration(Base):
    __tablename__ = "scoring_configurations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(80), unique=True)
    canonical_json: Mapped[str] = mapped_column(Text)
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    engine_version: Mapped[str] = mapped_column(String(80))


class Reviewed:
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_pseudonym_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    reviewer_role_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_snapshot: Mapped[dict] = mapped_column(JsonColumn, default=dict, nullable=False)


class Fact(Reviewed):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    statement: Mapped[str] = mapped_column(String(1000), nullable=False)
    completion: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=True)
    field: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    taxonomy_concept_id: Mapped[UUID] = mapped_column(ForeignKey("taxonomy_concepts.id", ondelete="SET NULL"), nullable=True)
    taxonomy_release_id: Mapped[UUID] = mapped_column(ForeignKey("taxonomy_versions.id", ondelete="SET NULL"), nullable=True)


def fact_checks():
    return (enum_check("review_status", REVIEW), enum_check("fact_type", ("occupation", "qualification", "experience")),
            enum_check("completion", ("unknown", "completed", "in_progress", "not_completed", "not_applicable")),
            CheckConstraint("duration_months IS NULL OR duration_months >= 0", name="ck_duration"))


class CandidateMatchingFact(Fact, TimestampMixin, Base):
    __tablename__ = "candidate_matching_facts"
    __table_args__ = fact_checks()
    candidate_profile_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"))
    cv_document_id: Mapped[UUID] = mapped_column(ForeignKey("cv_documents.id", ondelete="CASCADE"), nullable=True)
    provenance: Mapped[str] = mapped_column(String(30), default="candidate_confirmed")


class JobMatchingFact(Fact, TimestampMixin, Base):
    __tablename__ = "job_matching_facts"
    __table_args__ = (*fact_checks(), UniqueConstraint("id", "job_id", name="uq_job_fact_owner"))
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))


class JobRequirementGroup(Reviewed, TimestampMixin, Base):
    __tablename__ = "job_requirement_groups"
    __table_args__ = (
        UniqueConstraint("id", "job_id", name="uq_group_owner"),
        enum_check("review_status", REVIEW), enum_check("component", ("R", "P", "Q")),
        enum_check("operator", ("SINGLE", "OR", "AND")), enum_check("classification", CLASSIFICATION),
        CheckConstraint("NOT critical OR (classification = 'required' AND review_status = 'approved')", name="ck_critical"),
        CheckConstraint("(component = 'R' AND classification = 'required') OR (component = 'P' AND classification = 'preferred') OR (component = 'Q' AND classification IN ('required','preferred'))", name="ck_component_classification"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    component: Mapped[str] = mapped_column(String(1))
    operator: Mapped[str] = mapped_column(String(10))
    classification: Mapped[str] = mapped_column(String(30))
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64))


class JobRequirementGroupMember(Base):
    __tablename__ = "job_requirement_group_members"
    __table_args__ = (
        ForeignKeyConstraint(["group_id", "job_id"], ["job_requirement_groups.id", "job_requirement_groups.job_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["job_skill_id", "job_id"], ["job_skills.id", "job_skills.job_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["job_matching_fact_id", "job_id"], ["job_matching_facts.id", "job_matching_facts.job_id"], ondelete="CASCADE"),
        CheckConstraint("(job_skill_id IS NOT NULL AND job_matching_fact_id IS NULL) OR (job_skill_id IS NULL AND job_matching_fact_id IS NOT NULL)", name="ck_member_reference"),
        Index("uq_group_job_skill", "job_skill_id", unique=True, postgresql_where=text("job_skill_id IS NOT NULL"), sqlite_where=text("job_skill_id IS NOT NULL")),
        Index("uq_group_q_fact", "job_matching_fact_id", unique=True, postgresql_where=text("job_matching_fact_id IS NOT NULL"), sqlite_where=text("job_matching_fact_id IS NOT NULL")),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    group_id: Mapped[UUID] = mapped_column(ForeignKey("job_requirement_groups.id", ondelete="CASCADE"))
    job_skill_id: Mapped[UUID] = mapped_column(ForeignKey("job_skills.id", ondelete="CASCADE"), nullable=True)
    job_matching_fact_id: Mapped[UUID] = mapped_column(ForeignKey("job_matching_facts.id", ondelete="CASCADE"), nullable=True)


class JobInventoryReview(Reviewed, TimestampMixin, Base):
    __tablename__ = "job_inventory_reviews"
    __table_args__ = (
        enum_check("review_status", REVIEW), enum_check("o_applicability", APPLICABILITY), enum_check("q_applicability", APPLICABILITY),
        CheckConstraint("(o_applicability = 'not_applicable' AND o_reason IS NOT NULL AND o_reason = 'no_occupation_scope_stated') OR (o_applicability <> 'not_applicable' AND o_reason IS NULL)", name="ck_o_reason"),
        CheckConstraint("(q_applicability = 'not_applicable' AND q_reason IS NOT NULL AND q_reason = 'no_qualification_or_experience_scope_stated') OR (q_applicability <> 'not_applicable' AND q_reason IS NULL)", name="ck_q_reason"),
        CheckConstraint("NOT inventory_complete OR (review_status = 'approved' AND o_applicability <> 'unknown' AND q_applicability <> 'unknown')", name="ck_inventory_complete"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    inventory_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    o_applicability: Mapped[str] = mapped_column(String(20))
    o_reason: Mapped[str] = mapped_column(String(80), nullable=True)
    q_applicability: Mapped[str] = mapped_column(String(20))
    q_reason: Mapped[str] = mapped_column(String(80), nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64))


class JobOccurrenceReview(Reviewed, TimestampMixin, Base):
    """Inventory-only classifications, without rewriting Phase 5 JobSkill fields."""
    __tablename__ = "job_occurrence_reviews"
    __table_args__ = (enum_check("review_status", REVIEW), enum_check("classification", CLASSIFICATION),
        ForeignKeyConstraint(["job_skill_id", "job_id"], ["job_skills.id", "job_skills.job_id"], ondelete="CASCADE"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    job_skill_id: Mapped[UUID] = mapped_column(ForeignKey("job_skills.id", ondelete="CASCADE"), unique=True)
    classification: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(1000))
    source_fingerprint: Mapped[str] = mapped_column(String(64))


class MatchingRun(TimestampMixin, Base):
    __tablename__ = "matching_runs"
    __table_args__ = (
        enum_check("status", ("current", "stale", "historical", "unreplayable")),
        Index("uq_current_matching_run", "candidate_profile_id", "policy_id", unique=True,
              postgresql_where=text("is_current = true"), sqlite_where=text("is_current = 1")),
        CheckConstraint("NOT is_current OR status = 'current'", name="ck_run_current"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True)
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("scoring_configurations.id", ondelete="RESTRICT"))
    candidate_fingerprint: Mapped[str] = mapped_column(String(64))
    policy_fingerprint: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    universe_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pool_limit: Mapped[int] = mapped_column(Integer)
    stale_missing_job_count: Mapped[int] = mapped_column(Integer)


class JobMatchResult(TimestampMixin, Base):
    __tablename__ = "job_match_results"
    __table_args__ = (
        UniqueConstraint("run_id", "job_id", name="uq_run_job"),
        enum_check("status", ("ready", "provisional", "stale", "unreplayable")),
        CheckConstraint("alignment_value IS NULL OR alignment_value BETWEEN 0 AND 100", name="ck_alignment_range"),
        CheckConstraint("(alignment_value IS NULL) = (alignment_fraction IS NULL)", name="ck_alignment_null"),
        CheckConstraint("provisional = (alignment_value IS NULL)", name="ck_provisional_score"),
        CheckConstraint("phase6_fraction_valid(alignment_fraction, alignment_value)", name="ck_alignment_exact").ddl_if(dialect="postgresql"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("matching_runs.id", ondelete="CASCADE"))
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    job_fingerprint: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    alignment_fraction: Mapped[str] = mapped_column(String(160), nullable=True)
    alignment_value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    provisional: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20))
    retrieval_rank: Mapped[int] = mapped_column(Integer)
    retrieval_similarity: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_parameters: Mapped[dict] = mapped_column(JsonColumn, default=dict)


class MatchScoreComponent(Base):
    __tablename__ = "match_score_components"
    __table_args__ = (UniqueConstraint("result_id", "component", name="uq_result_component"),
                      CheckConstraint("status IN ('assessed','unassessed','not_applicable')", name="ck_component_status"),
                      CheckConstraint("denominator IS NULL OR denominator > 0", name="ck_component_denominator"),
                      CheckConstraint("value IS NULL OR value BETWEEN 0 AND 1", name="ck_component_value"),
                      CheckConstraint("effective_weight_value IS NULL OR effective_weight_value BETWEEN 0 AND 1", name="ck_component_weight"),
                      CheckConstraint("phase6_fraction_valid(value_fraction, value)", name="ck_component_exact").ddl_if(dialect="postgresql"),
                      CheckConstraint("phase6_fraction_valid(effective_weight_fraction, effective_weight_value)", name="ck_weight_exact").ddl_if(dialect="postgresql"),
                      enum_check("component", ("R", "P", "O", "Q")), enum_check("applicability", APPLICABILITY))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("job_match_results.id", ondelete="CASCADE"))
    component: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    applicability: Mapped[str] = mapped_column(String(20))
    numerator: Mapped[Decimal] = mapped_column(Numeric(160, 0), nullable=True)
    denominator: Mapped[Decimal] = mapped_column(Numeric(160, 0), nullable=True)
    base_weight: Mapped[int] = mapped_column(Integer)
    effective_weight_fraction: Mapped[str] = mapped_column(String(160), nullable=True)
    effective_weight_value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    value_fraction: Mapped[str] = mapped_column(String(160), nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_parameters: Mapped[dict] = mapped_column(JsonColumn, default=dict)


class SkillGapResult(Base):
    __tablename__ = "skill_gap_results"
    __table_args__ = (UniqueConstraint("result_id", "group_id", name="uq_result_gap"),
                      CheckConstraint("support_value IS NULL OR support_value BETWEEN 0 AND 1", name="ck_gap_support"),
                      CheckConstraint("phase6_fraction_valid(support_fraction, support_value)", name="ck_gap_exact").ddl_if(dialect="postgresql"),
                      enum_check("status", ("Matched", "Partially Covered", "Missing", "unassessed")))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    result_id: Mapped[UUID] = mapped_column(ForeignKey("job_match_results.id", ondelete="CASCADE"))
    group_id: Mapped[UUID] = mapped_column(ForeignKey("job_requirement_groups.id", ondelete="SET NULL"), nullable=True)
    support_fraction: Mapped[str] = mapped_column(String(160), nullable=True)
    support_value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    critical: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(30))
    evidence_snapshot: Mapped[dict] = mapped_column(JsonColumn, default=dict)
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_parameters: Mapped[dict] = mapped_column(JsonColumn, default=dict)


class SkillGapAtomicResult(Base):
    """Individual occurrence comparisons; group support is stored on SkillGapResult."""
    __tablename__ = "skill_gap_atomic_results"
    __table_args__ = (
        UniqueConstraint("gap_id", "member_id", "occurrence_fingerprint", name="uq_gap_atomic_occurrence"),
        CheckConstraint("support_value IS NULL OR support_value BETWEEN 0 AND 1", name="ck_atomic_support"),
        CheckConstraint("phase6_fraction_valid(support_fraction, support_value)", name="ck_atomic_exact").ddl_if(dialect="postgresql"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    gap_id: Mapped[UUID] = mapped_column(ForeignKey("skill_gap_results.id", ondelete="CASCADE"))
    member_id: Mapped[UUID] = mapped_column(ForeignKey("job_requirement_group_members.id", ondelete="SET NULL"), nullable=True)
    occurrence_fingerprint: Mapped[str] = mapped_column(String(64))
    support_fraction: Mapped[str] = mapped_column(String(160), nullable=True)
    support_value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_parameters: Mapped[dict] = mapped_column(JsonColumn, default=dict)

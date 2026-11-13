"""Owned reviewed-input persistence. Never touches embeddings or prototype matches."""
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import inspect, select, update, text
from sqlalchemy.orm import Session

from app.db.models import (CandidateProfile, CandidateSkill, CvDocument, Job, JobSkill,
    ApprovedTaxonomyLink, TaxonomyConcept, TaxonomyVersion, ExtractedCandidateTerm, ExtractedJobTerm)
from app.db.models.explainable import (CandidateMatchingFact, JobMatchingFact, JobRequirementGroup,
    JobRequirementGroupMember, JobOccurrenceReview, JobInventoryReview, MatchingRun, JobMatchResult)
from app.matching.policy import fingerprint


INPUT_LOCK_KEY = 603402


def lock_matching_inputs(db: Session) -> None:
    """Shared with the PostgreSQL source-write guard; never used by GETs."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": INPUT_LOCK_KEY})


def snapshot(row) -> dict:
    def value(item):
        # SQLite omits timezone information; persisted PostgreSQL timestamps are UTC-aware.
        return item.replace(tzinfo=timezone.utc) if isinstance(item, datetime) and item.tzinfo is None else item
    return {col.key: value(getattr(row, col.key)) for col in inspect(row).mapper.column_attrs}


class MatchingInputsRepository:
    def __init__(self, db: Session):
        self.db = db

    def profile(self, user_id: UUID, *, lock=False):
        if lock:
            lock_matching_inputs(self.db)
        query = select(CandidateProfile).where(CandidateProfile.user_id == user_id).execution_options(populate_existing=True)
        return self.db.scalar(query.with_for_update() if lock else query)

    def job(self, job_id: UUID, *, lock=False):
        if lock:
            lock_matching_inputs(self.db)
        query = select(Job).where(Job.id == job_id).execution_options(populate_existing=True)
        return self.db.scalar(query.with_for_update() if lock else query)

    def rows(self, model, **where):
        query = select(model).filter_by(**where).execution_options(populate_existing=True)
        return list(self.db.scalars(query.order_by(model.id)))

    def taxonomy(self, skills, source, facts=()):
        term_model = ExtractedCandidateTerm if source == "candidate" else ExtractedJobTerm
        terms = list(self.db.scalars(select(term_model).where(term_model.id.in_(
            [x.extracted_term_id for x in skills if x.extracted_term_id])).order_by(term_model.id)))
        links = list(self.db.scalars(select(ApprovedTaxonomyLink).where(
            ApprovedTaxonomyLink.term_source == source,
            ApprovedTaxonomyLink.extracted_term_id.in_([x.extracted_term_id for x in skills if x.extracted_term_id])
        ).order_by(ApprovedTaxonomyLink.id)))
        concepts = list(self.db.scalars(select(TaxonomyConcept).where(
            TaxonomyConcept.id.in_([x.concept_id for x in links] + [x.taxonomy_concept_id for x in facts if x.taxonomy_concept_id])).order_by(TaxonomyConcept.id)))
        versions = list(self.db.scalars(select(TaxonomyVersion).where(
            TaxonomyVersion.id.in_([x.taxonomy_version_id for x in concepts])).order_by(TaxonomyVersion.id)))
        return {"links": [snapshot(x) for x in links], "concepts": [snapshot(x) for x in concepts],
                "releases": [snapshot(x) for x in versions], "terms": [snapshot(x) for x in terms]}

    def candidate_state(self, profile):
        facts = self.rows(CandidateMatchingFact, candidate_profile_id=profile.id)
        skills = self.rows(CandidateSkill, candidate_profile_id=profile.id)
        cvs = self.rows(CvDocument, candidate_profile_id=profile.id)
        data = {"profile": snapshot(profile), "facts": [snapshot(x) for x in facts],
                "taxonomy": self.taxonomy(skills, "candidate", facts),
                "skills": [snapshot(x) for x in skills],
                "sources": [{"id": x.id, "raw_hash": fingerprint(x.raw_text),
                             "cleaned_hash": fingerprint(x.cleaned_text)} for x in cvs]}
        return {"fingerprint": fingerprint(data), **data}

    def job_state(self, job):
        skills = self.rows(JobSkill, job_id=job.id)
        facts = self.rows(JobMatchingFact, job_id=job.id)
        groups = self.rows(JobRequirementGroup, job_id=job.id)
        occurrences = self.rows(JobOccurrenceReview, job_id=job.id)
        members = list(self.db.scalars(select(JobRequirementGroupMember).where(
            JobRequirementGroupMember.group_id.in_([x.id for x in groups])
        ).order_by(JobRequirementGroupMember.id)))
        source = fingerprint({"job": snapshot(job), "skills": [snapshot(x) for x in skills],
                              "taxonomy": self.taxonomy(skills, "job")})
        data = {"source": source, "facts": [snapshot(x) for x in facts],
                "groups": [snapshot(x) for x in groups], "members": [snapshot(x) for x in members],
                "occurrences": [snapshot(x) for x in occurrences],
                "fact_taxonomy": self.taxonomy([], "job", facts)}
        current_hash = fingerprint(data)
        review = self.db.scalar(select(JobInventoryReview).where(JobInventoryReview.job_id == job.id))
        return {"fingerprint": current_hash, "source_fingerprint": source,
                "taxonomy": self.taxonomy(skills, "job"),
                "skills": [snapshot(x) for x in skills], **{k: v for k, v in data.items() if k != "source"},
                "inventory": snapshot(review) if review else None,
                "inventory_current": bool(review and review.inventory_complete and review.source_fingerprint == current_hash)}

    def invalidate_candidate(self, profile_id):
        run_ids = list(self.db.scalars(select(MatchingRun.id).where(
            MatchingRun.candidate_profile_id == profile_id, MatchingRun.is_current.is_(True))))
        self.db.execute(update(JobMatchResult).where(JobMatchResult.run_id.in_(run_ids)).values(status="stale"))
        self.db.execute(update(MatchingRun).where(MatchingRun.candidate_profile_id == profile_id,
            MatchingRun.is_current.is_(True)).values(is_current=False, status="stale"))

    def invalidate_job(self, job_id):
        run_ids = list(self.db.scalars(select(MatchingRun.id).join(JobMatchResult).where(
            JobMatchResult.job_id == job_id, MatchingRun.is_current.is_(True), MatchingRun.status == "current")))
        self.db.execute(update(JobMatchResult).where(JobMatchResult.run_id.in_(run_ids)).values(status="stale"))
        self.db.execute(update(MatchingRun).where(MatchingRun.id.in_(run_ids)).values(is_current=False, status="stale"))

    def finish(self):
        """One commit boundary, also a focused failure-injection seam for rollback tests."""
        self.db.flush()
        self.db.commit()

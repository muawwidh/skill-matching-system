from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import (ApprovedTaxonomyLink, CandidateProfileEmbedding, CandidateSkill,
                           ExtractedCandidateTerm, ExtractedJobTerm, Job, JobEmbedding, JobSkill)
from app.retrieval.representation import (MODEL_ID, MODEL_REVISION, TEMPLATE_V1, resolve_template,
    build_candidate_representation, build_job_representation)
from app.retrieval.embedder import load_local_tokenizer


class RetrievalRepository:
    def __init__(self, db: Session, template_version: str | None = None, tokenizer=None) -> None:
        self.db = db
        self.template_version = resolve_template(template_version)
        self.tokenizer = tokenizer

    def _canonicals(self, term_source: str, term_ids: list[UUID]) -> dict[UUID, tuple[str, str]]:
        if not term_ids:
            return {}
        result = {}
        for link in self.db.scalars(select(ApprovedTaxonomyLink).where(
            ApprovedTaxonomyLink.term_source == term_source,
            ApprovedTaxonomyLink.extracted_term_id.in_(term_ids),
        )):
            concept = link.concept
            release = concept.taxonomy_version
            if release.status == "active":
                result[link.extracted_term_id] = (concept.preferred_label, str(release.id))
        return result

    def profile_input(self, profile_id: UUID):
        skills = list(self.db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_profile_id == profile_id)))
        term_ids = [item.extracted_term_id for item in skills if item.extracted_term_id]
        canonicals = self._canonicals("candidate", term_ids)
        rows = []
        for skill in skills:
            canonical, release = canonicals.get(skill.extracted_term_id, ("", ""))
            if skill.extracted_term_id and canonical:
                term = self.db.get(ExtractedCandidateTerm, skill.extracted_term_id)
                if not term or (skill.raw_text, skill.normalized_text, skill.skill_type) != (
                        term.raw_text, term.normalized_text, term.term_type):
                    canonical, release = "", ""
            rows.append({"id": str(skill.id), "text": skill.raw_text, "normalized": skill.normalized_text,
                         "type": skill.skill_type, "status": skill.review_status,
                         "evidence": skill.evidence_sentence, "canonical": canonical,
                         "release": release, "term_id": str(skill.extracted_term_id or "")})
        return build_candidate_representation(rows, self.template_version)

    def job_input(self, job: Job):
        skills = list(self.db.scalars(select(JobSkill).where(JobSkill.job_id == job.id)))
        canonicals = self._canonicals("job", [item.extracted_term_id for item in skills if item.extracted_term_id])
        rows = []
        for skill in skills:
            canonical, release = canonicals.get(skill.extracted_term_id, ("", ""))
            if skill.extracted_term_id and canonical:
                term = self.db.get(ExtractedJobTerm, skill.extracted_term_id)
                if not term or (skill.raw_text, skill.normalized_text, skill.skill_type) != (
                        term.raw_text, term.normalized_text, term.term_type):
                    canonical, release = "", ""
            rows.append({"id": str(skill.id), "text": skill.raw_text, "normalized": skill.normalized_text,
                         "type": skill.skill_type, "requirement": skill.requirement_type,
                         "status": skill.review_status, "canonical": canonical,
                         "release": release, "term_id": str(skill.extracted_term_id or "")})
        source = {"title": job.title, "employment_type": job.employment_type,
                  "location": job.location, "company": job.company,
                  "description": job.cleaned_description,
                  "status": job.status}
        if self.template_version == TEMPLATE_V1:
            return build_job_representation(source, rows, [], self.template_version)
        sections = [{"id": str(s.id), "section_type": s.section_type, "heading": s.heading,
                     "content": s.content, "start_char": s.start_char, "end_char": s.end_char,
                     "confidence_score": s.confidence_score, "extraction_method": s.extraction_method}
                    for s in job.sections]
        if self.tokenizer is None:
            self.tokenizer = load_local_tokenizer()
        return build_job_representation(source, rows, sections, self.template_version, self.tokenizer)

    def invalidate_profile(self, profile_id: UUID) -> None:
        self.db.execute(update(CandidateProfileEmbedding).where(
            CandidateProfileEmbedding.candidate_profile_id == profile_id,
        ).values(status="stale"))

    def invalidate_job(self, job_id: UUID) -> None:
        self.db.execute(update(JobEmbedding).where(JobEmbedding.job_id == job_id).values(status="stale"))

    def invalidate_term(self, term_source: str, term_id: UUID) -> None:
        if term_source == "candidate":
            profile_id = self.db.scalar(select(CandidateSkill.candidate_profile_id).where(
                CandidateSkill.extracted_term_id == term_id).limit(1))
            if profile_id:
                self.invalidate_profile(profile_id)
        elif term_source == "job":
            job_id = self.db.scalar(select(ExtractedJobTerm.job_id).where(ExtractedJobTerm.id == term_id))
            if job_id:
                self.invalidate_job(job_id)

    def invalidate_all(self) -> None:
        self.db.execute(update(CandidateProfileEmbedding).values(status="stale"))
        self.db.execute(update(JobEmbedding).values(status="stale"))

    def mark_failed(self, owner_id: UUID, owner_kind: str) -> None:
        cls = CandidateProfileEmbedding if owner_kind == "profile" else JobEmbedding
        key = "candidate_profile_id" if owner_kind == "profile" else "job_id"
        self.db.execute(update(cls).where(getattr(cls, key) == owner_id,
            cls.model_id == MODEL_ID, cls.model_revision == MODEL_REVISION,
            cls.template_version == self.template_version, cls.status == "stale").values(status="failed"))

    def upsert(self, owner_id: UUID, owner_kind: str, value, embedding: list[float]) -> None:
        cls = CandidateProfileEmbedding if owner_kind == "profile" else JobEmbedding
        key = "candidate_profile_id" if owner_kind == "profile" else "job_id"
        row = self.db.scalar(select(cls).where(getattr(cls, key) == owner_id,
                cls.model_id == MODEL_ID, cls.model_revision == MODEL_REVISION,
                cls.template_version == self.template_version).with_for_update())
        if row is None:
            row = cls(**{key: owner_id}, model_id=MODEL_ID, model_revision=MODEL_REVISION,
                      template_version=self.template_version)
            self.db.add(row)
        row.embedding = embedding
        row.source_hash = value.source_hash
        row.taxonomy_fingerprint = value.taxonomy_fingerprint
        row.status = "ready"
        row.indexed_at = datetime.now(timezone.utc)
        self.db.flush()

    def profile_embedding(self, profile_id: UUID):
        return self.db.scalar(select(CandidateProfileEmbedding).where(
            CandidateProfileEmbedding.candidate_profile_id == profile_id,
            CandidateProfileEmbedding.model_id == MODEL_ID,
            CandidateProfileEmbedding.model_revision == MODEL_REVISION,
            CandidateProfileEmbedding.template_version == self.template_version))

    def exact_jobs(self, query, limit: int, offset: int = 0):
        if (query.template_version, query.model_id, query.model_revision) != (
                self.template_version, MODEL_ID, MODEL_REVISION):
            raise ValueError("Query embedding model/template does not match retrieval configuration")
        distance = JobEmbedding.embedding.cosine_distance(query.embedding)
        return self.db.execute(select(JobEmbedding, Job, distance.label("distance"))
            .join(Job, Job.id == JobEmbedding.job_id)
            .where(JobEmbedding.status == "ready", JobEmbedding.model_id == MODEL_ID,
                   JobEmbedding.model_revision == MODEL_REVISION,
                   JobEmbedding.template_version == self.template_version,
                   Job.status == "processed")
            .order_by(distance, Job.id).offset(offset).limit(limit)).all()

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, Job, User
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.embedder import Embedder
from app.retrieval.representation import DIMENSION


PROFILE_STATUS_DETAIL = {
    "profile_not_ready": "Candidate profile is not ready for retrieval.",
    "no_approved_skills": "Approve at least one extracted skill before retrieval.",
    "profile_not_indexed": "Candidate profile index is missing or stale. Run the indexing command.",
}


@dataclass(frozen=True)
class IndexResult:
    outcome: str
    source_hash: str | None


class RetrievalService:
    def __init__(self, db: Session, template_version: str | None = None, tokenizer=None) -> None:
        self.db = db
        self.repository = RetrievalRepository(db, template_version, tokenizer)

    def index_profile(self, profile_id: UUID, embedder: Embedder) -> IndexResult:
        profile = self.db.get(CandidateProfile, profile_id)
        if not profile or profile.status != "active" or not profile.consent_to_process_cv:
            return IndexResult("not_ready", None)
        value = self.repository.profile_input(profile_id)
        if value is None:
            self.repository.invalidate_profile(profile_id)
            return IndexResult("not_ready", None)
        existing = self.repository.profile_embedding(profile_id)
        if existing and existing.status == "ready" and existing.source_hash == value.source_hash:
            return IndexResult("unchanged", value.source_hash)
        vector = embedder.encode(value.text)
        self._validate(vector)
        self.repository.upsert(profile_id, "profile", value, vector)
        return IndexResult("indexed", value.source_hash)

    def index_job(self, job_id: UUID, embedder: Embedder) -> IndexResult:
        job = self.db.get(Job, job_id)
        if not job or job.status != "processed":
            self.repository.invalidate_job(job_id)
            return IndexResult("not_ready", None)
        value = self.repository.job_input(job)
        existing = self.db.scalar(self._job_embedding_query(job_id))
        if existing and existing.status == "ready" and existing.source_hash == value.source_hash:
            return IndexResult("unchanged", value.source_hash)
        vector = embedder.encode(value.text)
        self._validate(vector)
        self.repository.upsert(job_id, "job", value, vector)
        return IndexResult("indexed", value.source_hash)

    def _job_embedding_query(self, job_id):
        from sqlalchemy import select
        from app.db.models import JobEmbedding
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION
        return select(JobEmbedding).where(JobEmbedding.job_id == job_id,
            JobEmbedding.model_id == MODEL_ID, JobEmbedding.model_revision == MODEL_REVISION,
            JobEmbedding.template_version == self.repository.template_version)

    @staticmethod
    def _validate(vector: list[float]) -> None:
        from math import isfinite
        if len(vector) != DIMENSION or not all(isfinite(x) for x in vector) or not any(vector):
            raise ValueError("Embedder returned an invalid 384-dimensional vector.")

    def profile_readiness(self, user: User) -> tuple[str, object | None]:
        """Why a candidate's profile can or cannot be used for retrieval.

        Returns (status, query embedding). Status is one of PROFILE_STATUSES; the
        embedding is set only for "ready".
        """
        from sqlalchemy import select

        profile = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if not profile or profile.status != "active" or not profile.consent_to_process_cv:
            return "profile_not_ready", None
        source = self.repository.profile_input(profile.id)
        if source is None:
            return "no_approved_skills", None
        query = self.repository.profile_embedding(profile.id)
        if not query or query.status != "ready" or query.source_hash != source.source_hash:
            return "profile_not_indexed", None
        return "ready", query

    def jobs_for_user(self, user: User, limit: int, sources=None, exclude_sources=None) -> list[dict]:
        state, query = self.profile_readiness(user)
        if state != "ready":
            raise HTTPException(status_code=409, detail=PROFILE_STATUS_DETAIL[state])
        return self.retrieve(query, limit, sources, exclude_sources)

    def retrieve(self, query, limit: int, sources=None, exclude_sources=None) -> list[dict]:
        """Top-`limit` processed jobs by exact cosine similarity; jobs with stale vectors are skipped.

        `sources` restricts the search to those job sources (offline evaluation: only
        "evaluation"); `exclude_sources` leaves sources out (candidate view, D056).
        """
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION

        results = []
        offset = 0
        while len(results) < limit:
            rows = self.repository.exact_jobs(query, limit=100, offset=offset, sources=sources,
                                              exclude_sources=exclude_sources)
            if not rows:
                break
            offset += len(rows)
            for indexed, job, distance in rows:
                if indexed.source_hash != self.repository.job_input(job).source_hash:
                    continue
                results.append({"rank": len(results) + 1, "job_id": job.id, "title": job.title,
                    "company": job.company, "location": job.location, "employment_type": job.employment_type,
                    "retrieval_similarity": 1.0 - float(distance), "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION, "template_version": self.repository.template_version,
                    "candidate_input_hash": query.source_hash, "job_input_hash": indexed.source_hash,
                    "candidate_indexed_at": query.indexed_at, "job_indexed_at": indexed.indexed_at})
                if len(results) == limit:
                    break
        return results

    def ready_job_ids(self, exclude_sources=None) -> set[UUID]:
        """Processed jobs with a stored `ready` vector for the current model, revision and template.

        One query on stored status, no representation is rebuilt. Status stays current
        because every job change marks its vector stale and re-embeds it (D046).
        """
        from sqlalchemy import select
        from app.db.models import JobEmbedding
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION

        statement = (select(Job.id).join(JobEmbedding, JobEmbedding.job_id == Job.id)
                     .where(Job.status == "processed", JobEmbedding.status == "ready",
                            JobEmbedding.model_id == MODEL_ID, JobEmbedding.model_revision == MODEL_REVISION,
                            JobEmbedding.template_version == self.repository.template_version))
        if exclude_sources:
            statement = statement.where(Job.source.not_in(sorted(exclude_sources)))
        return set(self.db.scalars(statement))

    def fresh_job_ids(self, exclude_sources=None) -> set[UUID]:
        """IDs of processed jobs with a ready vector whose hash equals the current input.

        Raises RuntimeError when template v2 cannot be built (pinned tokenizer missing).
        """
        from sqlalchemy import select

        fresh = set()
        jobs = select(Job).where(Job.status == "processed")
        if exclude_sources:
            jobs = jobs.where(Job.source.not_in(sorted(exclude_sources)))
        for job in self.db.scalars(jobs):
            existing = self.db.scalar(self._job_embedding_query(job.id))
            if existing and existing.status == "ready" and \
                    existing.source_hash == self.repository.job_input(job).source_hash:
                fresh.add(job.id)
        return fresh

    def index_overview(self) -> dict:
        """Read-only index coverage for the configured model and template.

        Eligibility and freshness mirror `index_profile`, `index_job` and
        `jobs_for_user`: "indexed" means a ready vector whose source hash
        equals the current input, so stale vectors are not counted.
        """
        from sqlalchemy import select
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION

        profiles = {"eligible": 0, "indexed": 0}
        for profile in self.db.scalars(select(CandidateProfile)):
            if profile.status != "active" or not profile.consent_to_process_cv:
                continue
            value = self.repository.profile_input(profile.id)
            if value is None:
                continue
            profiles["eligible"] += 1
            existing = self.repository.profile_embedding(profile.id)
            if existing and existing.status == "ready" and existing.source_hash == value.source_hash:
                profiles["indexed"] += 1

        eligible_jobs = list(self.db.scalars(select(Job).where(Job.status == "processed")))
        jobs: dict = {"eligible": len(eligible_jobs), "indexed": 0}
        note = ""
        try:
            for job in eligible_jobs:
                existing = self.db.scalar(self._job_embedding_query(job.id))
                if existing and existing.status == "ready" and \
                        existing.source_hash == self.repository.job_input(job).source_hash:
                    jobs["indexed"] += 1
        except RuntimeError:
            # Template v2 job freshness needs the pinned local tokenizer.
            jobs["indexed"] = None
            note = "Job index freshness unavailable: pinned local tokenizer not found."
        return {"model_id": MODEL_ID, "model_revision": MODEL_REVISION,
                "template_version": self.repository.template_version,
                "profiles": profiles, "jobs": jobs, "note": note}

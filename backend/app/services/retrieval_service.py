from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, Job, User
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.embedder import Embedder
from app.retrieval.representation import DIMENSION


@dataclass(frozen=True)
class IndexResult:
    outcome: str
    source_hash: str | None


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RetrievalRepository(db)

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

    @staticmethod
    def _job_embedding_query(job_id):
        from sqlalchemy import select
        from app.db.models import JobEmbedding
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION
        return select(JobEmbedding).where(JobEmbedding.job_id == job_id,
            JobEmbedding.model_id == MODEL_ID, JobEmbedding.model_revision == MODEL_REVISION,
            JobEmbedding.template_version == TEMPLATE_VERSION)

    @staticmethod
    def _validate(vector: list[float]) -> None:
        from math import isfinite
        if len(vector) != DIMENSION or not all(isfinite(x) for x in vector) or not any(vector):
            raise ValueError("Embedder returned an invalid 384-dimensional vector.")

    def jobs_for_user(self, user: User, limit: int) -> list[dict]:
        from sqlalchemy import select
        from app.db.models import CandidateProfile
        from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION

        profile = self.db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if not profile or profile.status != "active" or not profile.consent_to_process_cv:
            raise HTTPException(status_code=409, detail="Candidate profile is not ready for retrieval.")
        source = self.repository.profile_input(profile.id)
        if source is None:
            raise HTTPException(status_code=409, detail="Approve at least one extracted skill before retrieval.")
        query = self.repository.profile_embedding(profile.id)
        if not query or query.status != "ready" or query.source_hash != source.source_hash:
            raise HTTPException(status_code=409, detail="Candidate profile index is missing or stale. Run the indexing command.")
        results = []
        offset = 0
        while len(results) < limit:
            rows = self.repository.exact_jobs(query, limit=100, offset=offset)
            if not rows:
                break
            offset += len(rows)
            for indexed, job, distance in rows:
                if indexed.source_hash != self.repository.job_input(job).source_hash:
                    continue
                results.append({"rank": len(results) + 1, "job_id": job.id, "title": job.title,
                    "company": job.company, "location": job.location, "employment_type": job.employment_type,
                    "retrieval_similarity": 1.0 - float(distance), "model_id": MODEL_ID,
                    "model_revision": MODEL_REVISION, "template_version": TEMPLATE_VERSION,
                    "candidate_input_hash": query.source_hash, "job_input_hash": indexed.source_hash,
                    "candidate_indexed_at": query.indexed_at, "job_indexed_at": indexed.indexed_at})
                if len(results) == limit:
                    break
        return results

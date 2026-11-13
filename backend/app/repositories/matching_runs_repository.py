"""Phase 6 run persistence and read-only provenance checks, not prototype matches."""
from uuid import UUID
import hashlib
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, Job, JobEmbedding, TaxonomyVersion
from app.db.models.explainable import (MatchingRun, JobMatchResult, ScoringConfiguration,
    MatchScoreComponent, SkillGapResult, SkillGapAtomicResult)
from app.matching.policy import CANONICAL_CONFIGURATION, POLICY_VERSION, POLICY_HASH, fingerprint, validate_configuration
from app.repositories.matching_inputs_repository import MatchingInputsRepository, snapshot, lock_matching_inputs
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import MODEL_ID, MODEL_REVISION, TEMPLATE_V2


class MatchingRunsRepository:
    def __init__(self, db: Session, tokenizer=None):
        self.db = db
        self.inputs = MatchingInputsRepository(db)
        self.retrieval = RetrievalRepository(db, TEMPLATE_V2, tokenizer)

    def configuration(self) -> ScoringConfiguration:
        row = self.db.scalar(select(ScoringConfiguration).where(
            ScoringConfiguration.version == POLICY_VERSION).execution_options(populate_existing=True))
        if row is None:
            raise ValueError("Matching policy is not installed")
        validate_configuration(row.canonical_json)
        if (row.policy_hash != POLICY_HASH or row.engine_version != POLICY_VERSION
                or row.canonical_json != CANONICAL_CONFIGURATION):
            raise ValueError("Installed matching policy identity is invalid")
        return row

    def profile(self, user_id: UUID, *, lock=False) -> CandidateProfile | None:
        return self.inputs.profile(user_id, lock=lock)

    @staticmethod
    def embedding_snapshot(row) -> dict | None:
        if row is None:
            return None
        data = snapshot(row)
        data["vector_sha256"] = fingerprint([float(x) for x in row.embedding])
        del data["embedding"]
        return data

    def capture(self, profile: CandidateProfile) -> dict:
        """No ranking or encoding. Include excluded states and every eligible source."""
        candidate = self.inputs.candidate_state(profile)
        candidate_input = self.retrieval.profile_input(profile.id)
        candidate_embedding = self.retrieval.profile_embedding(profile.id)
        releases = self.inputs.rows(TaxonomyVersion, status="active")
        selection = [snapshot(x) for x in releases]
        states, universe = {}, []
        missing, stale = 0, 0
        jobs = list(self.db.scalars(select(Job).where(Job.status == "processed").order_by(Job.id)
                                   .execution_options(populate_existing=True)))
        for job in jobs:
            self.db.expire(job, ["sections"])
            state = self.inputs.job_state(job)
            states[str(job.id)] = state
            value = self.retrieval.job_input(job)
            embedding = self.db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == job.id,
                JobEmbedding.template_version == TEMPLATE_V2, JobEmbedding.model_id == MODEL_ID,
                JobEmbedding.model_revision == MODEL_REVISION).execution_options(populate_existing=True))
            if embedding is None:
                missing += 1
            elif embedding.status != "ready" or embedding.source_hash != value.source_hash:
                stale += 1
            universe.append({"job_id": str(job.id), "reviewed_input_hash": state["fingerprint"],
                "inventory_hash": fingerprint(state["inventory"]),
                "representation_source_hash": value.source_hash,
                "representation_sha256": hashlib.sha256(value.text.encode()).hexdigest(),
                "embedding": self.embedding_snapshot(embedding)})
        candidate_ready = bool(profile.status == "active" and profile.consent_to_process_cv
            and candidate_input and candidate_embedding and candidate_embedding.status == "ready"
            and candidate_embedding.source_hash == candidate_input.source_hash)
        provenance = {"candidate_hash": candidate["fingerprint"],
            "candidate_embedding": self.embedding_snapshot(candidate_embedding),
            "candidate_representation_source_hash": candidate_input.source_hash if candidate_input else None,
            "taxonomy_selection": [{"id": str(x.id), "fingerprint": fingerprint(snapshot(x))} for x in releases],
            "universe": universe, "missing_job_embeddings": missing, "stale_job_embeddings": stale,
            "eligible_jobs": len(jobs), "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "template_version": TEMPLATE_V2, "engine_version": POLICY_VERSION, "policy_hash": POLICY_HASH,
            "engine_fingerprint": fingerprint({name: hashlib.sha256(
                (Path(__file__).parents[1] / "matching" / name).read_bytes()).hexdigest()
                for name in ("policy.py", "assessment.py")})}
        return {"candidate": candidate, "jobs": states, "releases": frozenset(str(x.id) for x in releases),
            "candidate_ready": candidate_ready, "provenance": provenance,
            "fingerprint": fingerprint(provenance), "universe_fingerprint": fingerprint(universe),
            "taxonomy_fingerprint": fingerprint(selection)}

    def lock(self, user_id: UUID) -> CandidateProfile | None:
        lock_matching_inputs(self.db)
        return self.profile(user_id, lock=True)

    def retire(self, profile_id: UUID, policy_id: UUID) -> None:
        self.db.execute(update(MatchingRun).where(MatchingRun.candidate_profile_id == profile_id,
            MatchingRun.policy_id == policy_id, MatchingRun.is_current.is_(True))
            .values(is_current=False, status="historical"))

    def run(self, run_id: UUID, profile_id: UUID) -> MatchingRun | None:
        return self.db.scalar(select(MatchingRun).where(MatchingRun.id == run_id,
            MatchingRun.candidate_profile_id == profile_id).execution_options(populate_existing=True))

    def current(self, profile_id: UUID) -> MatchingRun | None:
        # Return the latest attempt when invalidated, so GET can explain readiness
        # without creating a run or pretending the stale attempt is current.
        return self.db.scalar(select(MatchingRun).join(ScoringConfiguration).where(
            MatchingRun.candidate_profile_id == profile_id,
            ScoringConfiguration.version == POLICY_VERSION)
            .order_by(MatchingRun.is_current.desc(), MatchingRun.created_at.desc(), MatchingRun.id.desc())
            .limit(1).execution_options(populate_existing=True))

    def results(self, run_id: UUID) -> list[JobMatchResult]:
        return list(self.db.scalars(select(JobMatchResult).where(JobMatchResult.run_id == run_id)
                    .order_by(JobMatchResult.retrieval_rank).execution_options(populate_existing=True)))

    def components(self, result_id: UUID) -> list[MatchScoreComponent]:
        return list(self.db.scalars(select(MatchScoreComponent).where(MatchScoreComponent.result_id == result_id)
                    .order_by(MatchScoreComponent.component)))

    def gaps(self, result_id: UUID) -> list[SkillGapResult]:
        return list(self.db.scalars(select(SkillGapResult).where(SkillGapResult.result_id == result_id)
                    .order_by(SkillGapResult.group_id, SkillGapResult.id)))

    def atomic(self, gap_id: UUID) -> list[SkillGapAtomicResult]:
        return list(self.db.scalars(select(SkillGapAtomicResult).where(SkillGapAtomicResult.gap_id == gap_id)
                    .order_by(SkillGapAtomicResult.occurrence_fingerprint)))

    def add(self, row) -> None:
        self.db.add(row)

    def flush(self) -> None:
        self.db.flush()

    def refresh(self) -> None:
        self.db.expire_all()

    def rollback(self) -> None:
        self.db.rollback()

    def finish(self) -> None:
        self.db.flush()
        self.db.commit()

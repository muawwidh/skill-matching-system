"""Run guarantees against migrated, disposable PostgreSQL schemas and real pgvector."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile, CandidateProfileEmbedding, Job, JobEmbedding, User
from app.db.models.explainable import JobMatchResult, MatchingRun, SkillGapResult
from app.repositories.matching_inputs_repository import snapshot
from app.repositories.matching_runs_repository import MatchingRunsRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import DIMENSION, TEMPLATE_V2
from test_matching_runs import (
    RUN_TABLES, assert_complete, forbid_matching_inference, run_rows, runs_service, seed_runs, table_snapshot,
)
from test_taxonomy_postgres import pg_database  # noqa: F401


def test_postgres_real_vectors_nonnull_persistence_determinism_and_read_only_gets(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        user_id = users[0].id
        before = table_snapshot(db, exclude=RUN_TABLES)
        service = runs_service(db)
        first_response = service.create(users[0])
        first, = run_rows(db)
        first_id = first.id
        first_result = snapshot(assert_complete(db, first))
        assert first_response["readiness"]["ranking_evaluation_ready"] is False
        assert table_snapshot(db, exclude=RUN_TABLES) == before
    with Session(engine) as db:
        user = db.get(User, user_id)
        service = runs_service(db)
        before_get = table_snapshot(db)
        assert service.read(user, first_id) == first_response
        assert service.current(user) == first_response
        assert table_snapshot(db) == before_get
        service.create(user)
        rows = run_rows(db)
        assert len(rows) == 2 and sum(row.is_current for row in rows) == 1
        old = db.get(MatchingRun, first_id)
        current = next(row for row in rows if row.is_current)
        assert old.status == "historical" and not old.is_current
        assert old.input_fingerprint == current.input_fingerprint
        assert snapshot(db.get(JobMatchResult, first_result["id"])) == first_result
        result = assert_complete(db, current)
        for field in ("alignment_fraction", "alignment_value", "retrieval_rank", "retrieval_similarity", "job_fingerprint", "input_fingerprint"):
            assert getattr(result, field) == first_result[field]
        assert table_snapshot(db, exclude=RUN_TABLES) == before


def test_postgres_incomplete_inventory_is_provisional(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db, complete=False)
        response = runs_service(db).create(users[0])
        result = db.scalar(select(JobMatchResult))
        assert result.provisional and result.alignment_fraction is None and result.alignment_value is None
        assert response["readiness"]["score_ready_jobs"] == 0
        assert response["readiness"]["provisional_jobs"] == 1
        assert response["readiness"]["ranking_evaluation_ready"] is False


def test_postgres_missing_stale_job_vectors_counted_without_lexical_fallback(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        missing = Job(title="Unindexed synthetic job", description="Python", status="processed")
        stale = Job(title="Stale synthetic job", description="Python", status="processed")
        db.add_all([missing, stale])
        db.flush()
        repo = RetrievalRepository(db, TEMPLATE_V2)
        repo.upsert(stale.id, "job", repo.job_input(stale), [1.0] + [0.0] * (DIMENSION - 1))
        db.scalar(select(JobEmbedding).where(JobEmbedding.job_id == stale.id)).status = "stale"
        db.commit()
        runs_service(db).create(users[0])
        run, = run_rows(db)
        assert run.stale_missing_job_count == 2
        assert_complete(db, run)
        assert db.scalar(select(JobMatchResult).where(JobMatchResult.job_id.in_([missing.id, stale.id]))) is None


def test_postgres_missing_candidate_embedding_never_falls_back(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        db.delete(db.scalar(select(CandidateProfileEmbedding)))
        db.commit()
        before = table_snapshot(db)
        with pytest.raises(HTTPException) as error:
            runs_service(db).create(users[0])
        assert error.value.status_code == 409
    with Session(engine) as db:
        assert table_snapshot(db) == before


def test_postgres_finish_failure_rolls_back_previous_current_and_results(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        runs_service(db).create(users[0])
        before = table_snapshot(db)

        def fail(repo):
            repo.db.flush()
            raise RuntimeError("injected persisted run failure")

        monkeypatch.setattr(MatchingRunsRepository, "finish", fail)
        with pytest.raises(RuntimeError, match="injected persisted run failure"):
            runs_service(db).create(users[0])
    with Session(engine) as db:
        assert table_snapshot(db) == before


def test_postgres_create_holds_profile_and_source_write_locks(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, _ = seed_runs(db)
        profile_id, job_id = profiles[0].id, job.id
        original = MatchingRunsRepository.finish
        observed = []

        def probe(repo):
            # At the commit boundary another creator and a source writer must both wait.
            with Session(engine) as contender:
                contender.execute(text("SET LOCAL lock_timeout='100ms'"))
                with pytest.raises(DBAPIError) as error:
                    contender.execute(select(CandidateProfile).where(
                        CandidateProfile.id == profile_id).with_for_update())
                assert error.value.orig.sqlstate == "55P03"
                contender.rollback()
                contender.execute(text("SET LOCAL lock_timeout='100ms'"))
                with pytest.raises(DBAPIError) as error:
                    contender.execute(update(Job).where(Job.id == job_id).values(description="Concurrent source write"))
                assert error.value.orig.sqlstate == "55P03"
                contender.rollback()
            observed.append(True)
            original(repo)

        monkeypatch.setattr(MatchingRunsRepository, "finish", probe)
        runs_service(db).create(users[0])
        assert observed == [True]
    with Session(engine) as db:
        assert db.get(Job, job_id).description == "Requires Python"
        assert_complete(db, db.scalar(select(MatchingRun)))


def test_postgres_recheck_rejects_mixed_source_snapshot_and_rolls_back(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _ = seed_runs(db)
        runs_service(db).create(users[0])
        before = table_snapshot(db)
        original = MatchingRunsRepository.capture
        calls = []

        def capture(repo, profile):
            calls.append(True)
            if len(calls) == 2:
                # External writers are locked out; simulate a late same-transaction source change.
                repo.db.execute(update(Job).where(Job.id == job.id).values(description="Late synthetic change"))
                repo.db.flush()
            return original(repo, profile)

        monkeypatch.setattr(MatchingRunsRepository, "capture", capture)
        with pytest.raises(HTTPException) as error:
            runs_service(db).create(users[0])
        assert error.value.status_code == 409
        assert len(calls) >= 2
    with Session(engine) as db:
        assert table_snapshot(db) == before


def test_postgres_vector_replacement_detected_fresh_session_without_read_writes(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        runs_service(db).create(users[0])
        run, = run_rows(db)
        run_id, user_id = run.id, users[0].id
        row = db.scalar(select(JobEmbedding))
        row.embedding = [0.0, 1.0] + [0.0] * (DIMENSION - 2)
        db.commit()
    with Session(engine) as db:
        before = table_snapshot(db)
        user = db.get(User, user_id)
        service = runs_service(db)
        for response in (service.read(user, run_id), service.current(user)):
            assert response["current"] is False and response["status"] == "stale"
            assert response["results"][0]["alignment_score"] is None
            assert response["results"][0]["recorded_alignment_fraction"] == "100/1"
        assert table_snapshot(db) == before


@pytest.mark.parametrize("deleted_source", ["job", "profile"])
def test_postgres_source_deletion_redacts_history_preserving_arithmetic(pg_database, deleted_source):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, _ = seed_runs(db)
        runs_service(db).create(users[0])
        run, = run_rows(db)
        result = assert_complete(db, run)
        run_id, result_id = run.id, result.id
        db.delete(job if deleted_source == "job" else profiles[0])
        db.commit()
    with Session(engine) as db:
        run = db.get(MatchingRun, run_id)
        result = db.get(JobMatchResult, result_id)
        assert not run.is_current and run.status == "unreplayable"
        assert result.status == "unreplayable" and result.reason_parameters == {}
        assert result.alignment_fraction == "100/1" and result.alignment_value == Decimal("100")
        if deleted_source == "job":
            assert result.job_id is None
        else:
            assert run.candidate_profile_id is None
        gaps = list(db.scalars(select(SkillGapResult).where(SkillGapResult.result_id == result_id)))
        assert all(row.evidence_snapshot == {} and row.reason_parameters == {} for row in gaps)

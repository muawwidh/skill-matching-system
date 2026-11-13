"""Authoritative correction regressions; disposable PostgreSQL, never runtime data."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from alembic import command
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (ApprovedTaxonomyLink, CandidateProfileEmbedding, ExtractedJobTerm,
                           TaxonomyConcept, User)
from app.db.models.explainable import (JobRequirementGroup, JobRequirementGroupMember, JobMatchingFact,
                                       JobMatchResult, MatchingRun)
from app.repositories.matching_runs_repository import MatchingRunsRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import TEMPLATE_V2
from app.services.matching_inputs_service import MatchingInputsService
from app.services.matching_runs_service import MatchingRunsService
from test_matching_inputs import group_payload, sign_payload
from test_matching_inputs import seed
from test_matching_runs import RUN_TABLES, forbid_matching_inference, seed_runs, table_snapshot
from test_matching_run_corrections import two_jobs, inconsistent_capture, large_inputs, verify_bounds
from test_taxonomy_postgres import pg_database  # noqa: F401


def test_critical_database_check_agrees_with_schema_and_signoff(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _ = seed_runs(db)
        with pytest.raises(IntegrityError, match="ck_critical_required_skill"), db.begin_nested():
            db.add(JobRequirementGroup(job_id=job.id, component="Q", operator="SINGLE", classification="required",
                critical=True, source_fingerprint="0" * 64, **MatchingInputsService.review(users[1], "approved")))
            db.flush()
        group = db.scalar(select(JobRequirementGroup).where(JobRequirementGroup.job_id == job.id))
        group.critical = True; db.commit()
        service = MatchingInputsService(db)
        service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
        response = MatchingRunsService(db).create(users[0])
        assert response["results"][0]["alignment_fraction"] == "100/1"


def test_upgrade_rejects_existing_critical_q_without_coercion(pg_database):
    engine, config, _ = pg_database
    command.downgrade(config, "0009_explainable_matching")
    with Session(engine) as db:
        users, _, job, _ = seed(db)
        review = MatchingInputsService.review(users[1], "approved")
        fact = JobMatchingFact(id=uuid4(), job_id=job.id, fact_type="qualification", statement="Explicit qualification",
            completion="completed", field="engineering", scope="qualification", evidence_reference="synthetic line 1",
            source_fingerprint="0" * 64, **review)
        db.add(fact); db.flush()
        group = JobRequirementGroup(id=uuid4(), job_id=job.id, component="Q", operator="SINGLE", classification="required",
            critical=True, source_fingerprint="0" * 64, **review)
        db.add(group); db.flush()
        db.add(JobRequirementGroupMember(job_id=job.id, group_id=group.id, job_matching_fact_id=fact.id))
        db.commit(); group_id = group.id
    with pytest.raises(IntegrityError, match="ck_critical_required_skill"):
        command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0009_explainable_matching"
        row = conn.execute(text("SELECT component, critical FROM job_requirement_groups WHERE id=:id"), {"id": group_id}).one()
        assert tuple(row) == ("Q", True)


def test_inconsistent_job_does_not_abort_other_results_fresh_session(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, bad, good = two_jobs(db)
        bad_id, good_id, user_id = bad.id, good.id, users[0].id
        inconsistent_capture(monkeypatch, bad.id)
        response = MatchingRunsService(db).create(users[0])
        run_id = response["run_id"]
    with Session(engine) as db:
        rows = {x.job_id: x for x in db.scalars(select(JobMatchResult).where(JobMatchResult.run_id == run_id))}
        assert rows[bad_id].provisional and rows[bad_id].alignment_value is None
        assert rows[bad_id].reason_code == "invalid_critical_group"
        assert rows[good_id].alignment_fraction == "100/1"
        assert len(MatchingRunsService(db).read(db.get(User, user_id), run_id)["results"]) == 2


@pytest.mark.parametrize("grouped", [False, True])
def test_large_inputs_fit_real_snapshot_constraints_and_retain_all_occurrences(pg_database, grouped):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job = large_inputs(db, grouped=grouped)
        before = table_snapshot(db, exclude=RUN_TABLES)
        response = MatchingRunsService(db).create(users[0])
        run_id, user_id = response["run_id"], users[0].id
    with Session(engine) as db:
        verify_bounds(db)
        assert table_snapshot(db, exclude=RUN_TABLES) == before
        result, = MatchingRunsService(db).read(db.get(User, user_id), run_id)["results"]
        assert result["alignment_fraction"] == ("100/21" if grouped else None)
        assert len(result["gaps"]) == (21 if grouped else 20)


@pytest.mark.parametrize("rollback", [False, True])
def test_approved_link_change_transactionally_stales_current_runs(pg_database, rollback):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, skill = seed_runs(db)
        concept = db.scalar(select(TaxonomyConcept).where(TaxonomyConcept.preferred_label == "Python"))
        term = ExtractedJobTerm(job_id=job.id, raw_text="Python", normalized_text="python", term_type="skill",
                                extraction_method="synthetic-test", review_status="approved")
        db.add(term); db.flush(); skill.extracted_term_id = term.id
        link = ApprovedTaxonomyLink(term_source="job", extracted_term_id=term.id, concept_id=concept.id,
            match_method="exact_preferred", confidence_score=1, approval_source="human_review",
            approved_by=users[1].id, approved_at=datetime.now(timezone.utc))
        db.add(link); db.commit()
        inputs = MatchingInputsService(db)
        for group in inputs.read_job(job.id)["groups"]:
            inputs.delete_group(users[1], job.id, group["id"], inputs.read_job(job.id)["fingerprint"])
        inputs.create_group(users[1], job.id, group_payload(inputs.read_job(job.id), skill))
        inputs.signoff(users[1], job.id, sign_payload(inputs.read_job(job.id)))
        repo = RetrievalRepository(db, TEMPLATE_V2)
        repo.upsert(job.id, "job", repo.job_input(job), [1.] + [0.] * 383); db.commit()
        run_id = MatchingRunsService(db).create(users[0])["run_id"]
        before = table_snapshot(db)
        link.match_method = "human_review"; db.flush(); db.expire_all()
        assert not db.get(MatchingRun, run_id).is_current
        assert db.scalar(select(JobMatchResult).where(JobMatchResult.run_id == run_id)).status == "stale"
        if rollback: db.rollback()
        else: db.commit()
    with Session(engine) as db:
        if rollback:
            assert table_snapshot(db) == before
        else:
            assert not db.get(MatchingRun, run_id).is_current


def test_candidate_vector_hash_checked_independently_of_stored_stale_flags(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        run_id = MatchingRunsService(db).create(users[0])["run_id"]
        user_id = users[0].id
        vector = db.scalar(select(CandidateProfileEmbedding))
        original_source = vector.source_hash
        original_metadata = MatchingRunsRepository.embedding_snapshot(vector)
        db.execute(update(CandidateProfileEmbedding).where(CandidateProfileEmbedding.id == vector.id).values(
            embedding=[0., 1.] + [0.] * 382, updated_at=vector.updated_at))
        db.flush()
        # Deliberately corrupt only the invalidation cache, not the provenance.
        db.execute(update(MatchingRun).where(MatchingRun.id == run_id).values(status="current", is_current=True))
        db.execute(update(JobMatchResult).where(JobMatchResult.run_id == run_id).values(status="ready"))
        db.commit()
        assert vector.source_hash == original_source and vector.status == "ready"
        changed = MatchingRunsRepository.embedding_snapshot(vector)
        assert changed.pop("vector_sha256") != original_metadata.pop("vector_sha256")
        assert changed == original_metadata
    with Session(engine) as db:
        assert db.get(MatchingRun, run_id).is_current
        before = table_snapshot(db)
        response = MatchingRunsService(db).read(db.get(User, user_id), run_id)
        assert response["current"] is False
        assert response["results"][0]["alignment_fraction"] is None
        assert table_snapshot(db) == before


@pytest.mark.parametrize("conflict", [False, True])
def test_real_constraint_and_serialization_errors_are_distinguished_and_rolled_back(pg_database, monkeypatch, conflict):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, _, _ = seed_runs(db)
        MatchingRunsService(db).create(users[0]); before = table_snapshot(db)
        def fail(repo):
            if conflict:
                repo.db.execute(text("DO $$ BEGIN RAISE EXCEPTION USING ERRCODE='40001'; END $$"))
            else:
                repo.db.execute(update(JobMatchResult).values(alignment_value=101))
        monkeypatch.setattr(MatchingRunsRepository, "finish", fail)
        with pytest.raises(HTTPException) as error:
            MatchingRunsService(db).create(users[0])
        assert error.value.status_code == (409 if conflict else 422)
        assert error.value.detail["code"] == ("matching_concurrency_conflict" if conflict else "matching_persistence_constraint")
    with Session(engine) as db:
        assert table_snapshot(db) == before

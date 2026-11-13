"""Opt-in, isolated PostgreSQL checks for migration 0010. Synthetic inputs only."""
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CandidateSkill, CvDocument, CvSection, Job
from app.db.models.retrieval import CandidateProfileEmbedding, JobEmbedding
from app.db.models.explainable import (MatchScoreComponent, MatchingRun, JobMatchResult,
    JobRequirementGroup, JobRequirementGroupMember)
from app.repositories.matching_inputs_repository import snapshot
from test_matching_inputs import seed
from test_matching_inputs_postgres import run_result
from test_taxonomy_postgres import pg_database  # noqa: F401
from app.services.matching_inputs_service import MatchingInputsService


@pytest.mark.parametrize("numerator,denominator,exact,value,valid", [
    (0, 1, "0/1", 0, True), (1, 1, "1/1", 1, True),
    (1, 3, "1/3", Decimal(".333333"), True),
    (2, 6, "1/3", Decimal(".333333"), True),
    (None, None, None, None, True), (1, 1, None, None, False),
    (None, 3, "1/3", Decimal(".333333"), False),
    (1, None, "1/3", Decimal(".333333"), False),
    (1, 2, "1/3", Decimal(".333333"), False),
    (333333, 1000000, "1/3", Decimal(".333333"), False),
    (-1, 3, "1/3", Decimal(".333333"), False),
    (1, 0, "1/3", Decimal(".333333"), False),
    (Decimal("NaN"), Decimal("NaN"), "1/3", Decimal(".333333"), False),
])
def test_component_integer_ratio_agrees_exactly(pg_database, numerator, denominator, exact, value, valid):
    engine, _, _ = pg_database
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        _, result = run_result(db, profiles[0], job)
        db.add(MatchScoreComponent(result_id=result.id, component="R", applicability="applicable",
            status="unassessed" if exact is None else "assessed", numerator=numerator,
            denominator=denominator, value_fraction=exact, value=value, base_weight=7,
            reason_code="synthetic", reason_parameters={}))
        if valid:
            db.commit()
        else:
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()


@pytest.mark.parametrize("scope", ["profile", "skill", "cv", "section", "job_group", "job", "taxonomy",
                                  "profile_embedding", "job_embedding"])
@pytest.mark.parametrize("rollback", [False, True])
def test_input_triggers_scope_history_and_rollback(pg_database, scope, rollback):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, _ = seed(db)
        other_job = Job(title="Other synthetic job", description="Other", status="processed")
        cv = CvDocument(candidate_profile_id=profiles[0].id, content_type="text/plain", source="synthetic")
        skill = CandidateSkill(candidate_profile_id=profiles[0].id, raw_text="Python", normalized_text="python")
        db.add_all([other_job, cv, skill]); db.flush()
        section = CvSection(cv_document_id=cv.id, section_type="skills", content="Python")
        metadata = dict(embedding=[1.0] + [0.0] * 383, model_id="synthetic", model_revision="0" * 40,
                        template_version="synthetic", source_hash="0" * 64, taxonomy_fingerprint="0" * 64)
        profile_embedding = CandidateProfileEmbedding(candidate_profile_id=profiles[0].id, **metadata)
        job_embedding = JobEmbedding(job_id=job.id, **metadata)
        db.add_all([section, profile_embedding, job_embedding]); db.commit()
        old, old_result = run_result(db, profiles[0], job)
        old.is_current = False; old.status = "historical"; db.commit()
        current, current_result = run_result(db, profiles[0], job)
        other, other_result = run_result(db, profiles[3], other_job)
        db.commit()
        ids = current.id, current_result.id, other.id, other_result.id, old.id, old_result.id
        before = tuple(snapshot(row) for row in (current, current_result, other, other_result, old, old_result))
        if scope == "profile": profiles[0].headline = "Changed"
        elif scope == "skill": skill.review_status = "approved"
        elif scope == "cv": cv.cleaned_text = "Changed synthetic source"
        elif scope == "section": section.content = "Changed synthetic section"
        elif scope == "profile_embedding": profile_embedding.status = "stale"
        elif scope == "job_embedding": job_embedding.status = "stale"
        elif scope == "job_group":
            group = JobRequirementGroup(job_id=job.id, component="R", operator="SINGLE",
                classification="required", critical=False, source_fingerprint="0" * 64,
                **MatchingInputsService.review(users[1], "approved"))
            db.add(group); db.flush()
            db.add(JobRequirementGroupMember(group_id=group.id, job_id=job.id,
                job_skill_id=MatchingInputsService(db).read_job(job.id)["skills"][0]["id"]))
        elif scope == "job": job.description = "Changed synthetic job"
        else:
            db.execute(text("UPDATE taxonomy_versions SET checksum=:checksum"), {"checksum": "1" * 64})
        db.flush()
        # Check in-transaction invalidation before choosing commit versus rollback.
        db.expire_all()
        assert db.get(MatchingRun, ids[0]).status == "stale"
        assert db.get(JobMatchResult, ids[1]).status == "stale"
        all_current = scope in {"job", "taxonomy", "job_embedding"}
        assert db.get(MatchingRun, ids[2]).status == ("stale" if all_current else "current")
        assert db.get(JobMatchResult, ids[3]).status == ("stale" if all_current else "ready")
        if rollback: db.rollback()
        else: db.commit()
    with Session(engine) as db:
        rows = tuple(db.get(model, identity) for model, identity in zip(
            (MatchingRun, JobMatchResult, MatchingRun, JobMatchResult, MatchingRun, JobMatchResult), ids))
        assert tuple(snapshot(row) for row in rows[4:]) == before[4:]
        if rollback:
            assert tuple(snapshot(row) for row in rows) == before
        else:
            assert rows[0].status == rows[1].status == "stale"
            assert not rows[0].is_current


def test_mutation_gate_locks_even_empty_statements_until_transaction_ends(pg_database):
    engine, _, _ = pg_database
    with engine.connect() as writer, engine.connect() as observer:
        writer.execute(text("UPDATE candidate_skills SET review_status=review_status WHERE false"))
        assert not observer.scalar(text("SELECT pg_try_advisory_xact_lock(603402)"))
        observer.rollback()
        writer.rollback()
        assert observer.scalar(text("SELECT pg_try_advisory_xact_lock(603402)"))
        observer.rollback()


@pytest.mark.parametrize("event", ["insert", "delete", "move"])
def test_candidate_mutation_events_and_owner_reassignment(pg_database, event):
    engine, _, _ = pg_database
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        skill = CandidateSkill(candidate_profile_id=profiles[0].id, raw_text="Python", normalized_text="python")
        if event != "insert":
            db.add(skill); db.commit()
        run, result = run_result(db, profiles[0], job)
        other, other_result = run_result(db, profiles[3], job)
        db.commit()
        ids = run.id, result.id, other.id, other_result.id
        if event == "insert": db.add(skill)
        elif event == "delete": db.delete(skill)
        else: skill.candidate_profile_id = profiles[3].id
        db.commit()
    with Session(engine) as db:
        assert db.get(MatchingRun, ids[0]).status == db.get(JobMatchResult, ids[1]).status == "stale"
        expected = "stale" if event == "move" else "current"
        assert db.get(MatchingRun, ids[2]).status == expected
        assert db.get(JobMatchResult, ids[3]).status == ("stale" if event == "move" else "ready")


def test_populated_0009_upgrade_preserves_history_and_nullable_provenance(pg_database):
    engine, config, _ = pg_database
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        run, result = run_result(db, profiles[0], job)
        db.add(MatchScoreComponent(result_id=result.id, component="R", applicability="applicable",
            status="assessed", numerator=2, denominator=6, value_fraction="1/3", value=Decimal(".333333"),
            base_weight=7, reason_code="synthetic", reason_parameters={}))
        db.commit()
        identity = run.id
    command.downgrade(config, "0009_explainable_matching")
    with engine.connect() as conn:
        before = conn.execute(text("SELECT * FROM matching_runs WHERE id=:id"), {"id": identity}).mappings().one()
    command.upgrade(config, "head")
    with engine.connect() as conn:
        after = conn.execute(text("SELECT * FROM matching_runs WHERE id=:id"), {"id": identity}).mappings().one()
        assert dict(before) == {key: after[key] for key in before}
        assert after["engine_version"] is None and after["provenance_snapshot"] is None
        assert conn.scalar(text("SELECT numerator FROM match_score_components")) == 2
    command.downgrade(config, "0009_explainable_matching")
    assert "provenance_snapshot" not in {col["name"] for col in inspect(engine).get_columns("matching_runs")}
    command.upgrade(config, "head")


@pytest.mark.parametrize("table", ["candidate_profiles", "jobs", "taxonomy_versions"])
def test_noop_source_update_preserves_current_and_historical_snapshots(pg_database, table):
    engine, _, _ = pg_database
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        old, old_result = run_result(db, profiles[0], job)
        old.is_current = False
        old.status = "historical"
        db.commit()
        current, current_result = run_result(db, profiles[0], job)
        current.provenance_snapshot = {"source_hash": "0" * 64}
        db.commit()
        rows = (old, old_result, current, current_result)
        identities = tuple((type(row), row.id) for row in rows)
        before = tuple(snapshot(row) for row in rows)
        db.execute(text(f"UPDATE {table} SET status=status"))
        db.expire_all()
        assert tuple(snapshot(db.get(model, identity)) for model, identity in identities) == before
        assert db.get(MatchingRun, current.id).is_current
        db.commit()
    with Session(engine) as db:
        assert tuple(snapshot(db.get(model, identity)) for model, identity in identities) == before


def test_run_provenance_is_bounded(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        run, _ = run_result(db, profiles[0], job)
        run.provenance_snapshot = {"source_hash": "0" * 64, "release_ids": [str(uuid4())]}
        db.commit()
        run.provenance_snapshot = {"oversized_hashes": ["0" * 64] * 5000}
        with pytest.raises(IntegrityError): db.flush()
        db.rollback()

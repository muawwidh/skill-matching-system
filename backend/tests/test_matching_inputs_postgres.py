"""Authoritative FK, migration, audit, transaction and isolation checks; synthetic data only."""
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (CandidateJobMatch, CandidateProfile, CandidateProfileEmbedding, JobEmbedding, User, Job, JobSkill)
from app.db.models.explainable import (CandidateMatchingFact, JobMatchingFact, ScoringConfiguration,
    JobRequirementGroup, JobRequirementGroupMember, JobInventoryReview, MatchingRun, JobMatchResult,
    MatchScoreComponent, SkillGapResult)
from app.matching.policy import CANONICAL_CONFIGURATION, POLICY_HASH
from app.repositories.matching_inputs_repository import snapshot
from app.schemas.matching_inputs import FactInput, GroupInput
from app.services.matching_inputs_service import MatchingInputsService
from test_matching_inputs import seed, group_payload, sign_payload
from test_taxonomy_postgres import pg_database  # noqa: F401


NEW_TABLES={"scoring_configurations","candidate_matching_facts","job_matching_facts","job_requirement_groups",
            "job_requirement_group_members","job_inventory_reviews","job_occurrence_reviews","matching_runs",
            "job_match_results","match_score_components","skill_gap_results","skill_gap_atomic_results"}


def legacy_snapshot(engine):
    with engine.connect() as conn:
        names=set(inspect(conn).get_table_names())-NEW_TABLES-{"alembic_version"}
        return {name: sorted(json.dumps(dict(row),sort_keys=True,default=str) for row in conn.execute(text(f'SELECT * FROM "{name}"')).mappings()) for name in names}


def test_populated_0008_upgrade_downgrade_reupgrade_preserves_all_legacy_rows(pg_database):
    engine, config, _=pg_database
    command.downgrade(config,"0008_dense_retrieval")
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        db.add(CandidateJobMatch(candidate_profile_id=profiles[0].id,job_id=job.id,score=77,
                 matched_required=[],matched_preferred=[],missing_required=[],missing_preferred=[],
                 candidate_skill_count=1,job_skill_count=1,explanation="synthetic legacy"))
        db.commit()
    before=legacy_snapshot(engine)
    command.upgrade(config,"head")
    assert legacy_snapshot(engine)==before
    with Session(engine) as db:
        policy=db.scalar(select(ScoringConfiguration))
        assert policy.canonical_json==CANONICAL_CONFIGURATION and policy.policy_hash==POLICY_HASH
        assert set(inspect(engine).get_table_names())>=NEW_TABLES
    command.downgrade(config,"0008_dense_retrieval")
    assert not set(inspect(engine).get_table_names()) & NEW_TABLES
    assert legacy_snapshot(engine)==before
    command.upgrade(config,"head")
    assert legacy_snapshot(engine)==before


def test_policy_and_reviewer_snapshots_are_database_immutable(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        service=MatchingInputsService(db)
        created=service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
        group_id,reviewer_id=created["id"],users[1].id
        attribution=created["reviewer_pseudonym_snapshot"],created["reviewer_role_snapshot"]
    with Session(engine) as db:
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(update(ScoringConfiguration).values(engine_version="tampered"))
        with pytest.raises(DBAPIError),db.begin_nested():
            db.execute(update(JobRequirementGroup).where(JobRequirementGroup.id==group_id).values(reviewer_role_snapshot="tampered"))
        db.delete(db.get(User,reviewer_id));db.commit()
    with Session(engine) as db:
        group=db.get(JobRequirementGroup,group_id)
        assert group.reviewed_by is None
        assert (group.reviewer_pseudonym_snapshot,group.reviewer_role_snapshot)==attribution


def test_group_membership_global_exclusivity_and_cross_job_ownership(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        service=MatchingInputsService(db)
        service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
        with pytest.raises(Exception) as exc:
            service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
        assert exc.value.status_code==409
        other=Job(title="Other",description="Synthetic other job");db.add(other);db.commit()
        with pytest.raises(Exception) as exc:
            service.create_group(users[1],other.id,group_payload(service.read_job(other.id),skill))
        assert exc.value.status_code==404
        state=service.read_job(job.id)
        fact=service.create_fact(users[1],FactInput(expected_fingerprint=state["fingerprint"],
            fact_type="qualification",statement="Bachelor's floor",completion="completed",evidence_reference="source line 1",
            review_status="approved"),job.id)
        payload=lambda:GroupInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],component="Q",operator="SINGLE",
            classification="required",critical=False,review_status="approved",members=[{"job_matching_fact_id":fact["id"]}])
        service.create_group(users[1],job.id,payload())
        with pytest.raises(Exception) as exc: service.create_group(users[1],job.id,payload())
        assert exc.value.status_code==409
    with Session(engine) as db:
        assert len(list(db.scalars(select(JobRequirementGroupMember).where(JobRequirementGroupMember.job_matching_fact_id==fact["id"]))))==1


def run_result(db, profile, job):
    config=db.scalar(select(ScoringConfiguration))
    run=MatchingRun(candidate_profile_id=profile.id,policy_id=config.id,candidate_fingerprint="1"*64,
        policy_fingerprint=POLICY_HASH,input_fingerprint="2"*64,universe_fingerprint="3"*64,
        status="current",is_current=True,pool_limit=20,stale_missing_job_count=0)
    db.add(run);db.flush()
    result=JobMatchResult(run_id=run.id,job_id=job.id,job_fingerprint="4"*64,input_fingerprint="5"*64,
        alignment_fraction="100/1",alignment_value=100,provisional=False,status="ready",retrieval_rank=1,
        retrieval_similarity=.8,reason_code="candidate_confirmed",reason_parameters={})
    db.add(result);db.flush()
    return run,result


def test_input_failure_rolls_back_downstream_state_from_fresh_session(pg_database,monkeypatch):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        run,result=run_result(db,profiles[0],job)
        db.commit()
        before_run=snapshot(run);before_result=snapshot(result)
        job_id,run_id,result_id=job.id,run.id,result.id
        before=legacy_snapshot(engine)
        service=MatchingInputsService(db)
        def fail():
            db.flush()
            raise RuntimeError("after writes and invalidation")
        monkeypatch.setattr(service.repo,"finish",fail)
        with pytest.raises(RuntimeError): service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
    with Session(engine) as db:
        assert snapshot(db.get(MatchingRun,run_id))==before_run
        assert snapshot(db.get(JobMatchResult,result_id))==before_result
        assert not list(db.scalars(select(JobRequirementGroup).where(JobRequirementGroup.job_id==job_id)))
    assert legacy_snapshot(engine)==before


def test_current_run_partial_unique_index_and_job_erasure(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        run,result=run_result(db,profiles[0],job);db.commit()
        with pytest.raises(IntegrityError),db.begin_nested(): run_result(db,profiles[0],job)
        ids=run.id,result.id,job.id
        db.delete(job);db.commit()
    with Session(engine) as db:
        run=db.get(MatchingRun,ids[0]);result=db.get(JobMatchResult,ids[1])
        assert run.status=="unreplayable" and not run.is_current
        assert result.job_id is None and result.status=="unreplayable" and result.reason_parameters=={}


def test_complete_inventory_fresh_session_noop_and_source_invalidation(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        service=MatchingInputsService(db)
        service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
        first=service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        job_id,user_id=job.id,users[1].id
    with Session(engine) as db:
        service=MatchingInputsService(db)
        assert service.read_job(job_id)["inventory_current"]
        second=service.signoff(db.get(User,user_id),job_id,sign_payload(service.read_job(job_id)))
        assert second==first
        job=db.get(Job,job_id);job.description="Changed source";db.commit()
    with Session(engine) as db:
        assert not MatchingInputsService(db).read_job(job_id)["inventory_current"]


def test_database_rejects_empty_groups_and_noncanonical_review(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        review=MatchingInputsService.review(users[1],"approved")
        with pytest.raises(DBAPIError):
            db.add(JobRequirementGroup(job_id=job.id,component="R",operator="SINGLE",classification="required",
                critical=False,source_fingerprint="0"*64,**review));db.commit()
        db.rollback()
        with pytest.raises(IntegrityError),db.begin_nested():
            db.add(CandidateMatchingFact(candidate_profile_id=profiles[0].id,fact_type="qualification",statement="x",
                completion="unknown",field="",scope="",evidence_reference="x",source_fingerprint="0"*64,
                **{**review,"review_status":"Approved"}));db.flush()


def test_profile_row_lock_serializes_input_writes(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        user_id=users[0].id
    with Session(engine) as first,Session(engine) as second:
        service=MatchingInputsService(first)
        cached=service.profile(first.get(User,user_id))
        other=second.get(CandidateProfile,cached.id)
        other.headline="Concurrent reviewed profile change";second.commit()
        assert service.profile(first.get(User,user_id),True).headline=="Concurrent reviewed profile change"
        service.profile(first.get(User,user_id),True)
        second.execute(text("SET LOCAL lock_timeout='100ms'"))
        with pytest.raises(DBAPIError):
            MatchingInputsService(second).profile(second.get(User,user_id),True)
        second.rollback()
        first.rollback()


def test_postgres_api_role_matrix_and_read_only_gets(pg_database):
    from test_matching_inputs import test_input_api_role_matrix_and_ownership, test_all_reviewed_input_mutations_authoritative_role_guards
    engine,_,_=pg_database
    with Session(engine) as db:
        test_input_api_role_matrix_and_ownership(db)
        test_all_reviewed_input_mutations_authoritative_role_guards(db)


def test_successful_reviewed_input_writes_preserve_all_phase4_phase5_and_legacy_tables(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        common=dict(embedding=[1.0]+[0.0]*383,model_id="synthetic-test-only",model_revision="f"*40,
                    template_version="e5-job-profile-v2",source_hash="1"*64,taxonomy_fingerprint="2"*64,status="ready")
        db.add_all([CandidateProfileEmbedding(candidate_profile_id=profiles[0].id,**common),
                    JobEmbedding(job_id=job.id,**common),CandidateJobMatch(candidate_profile_id=profiles[0].id,
                    job_id=job.id,score=77,matched_required=[],matched_preferred=[],missing_required=[],
                    missing_preferred=[],candidate_skill_count=1,job_skill_count=1,explanation="legacy")])
        run,result=run_result(db,profiles[0],job);db.commit()
        ids=job.id,run.id
        before=legacy_snapshot(engine)
        service=MatchingInputsService(db)
        service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
        service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        state=service.read_candidate(users[0])
        service.create_fact(users[0],FactInput(expected_fingerprint=state["fingerprint"],fact_type="experience",
            statement="Candidate-confirmed supervised practice",completion="unknown",duration_months=6,
            scope="supervised",evidence_reference="synthetic CV line 1",review_status="approved"))
    assert legacy_snapshot(engine)==before
    with Session(engine) as db:
        assert db.get(MatchingRun,ids[1]).status=="stale"
        assert not db.get(MatchingRun,ids[1]).is_current


def test_inventory_database_reason_constraints_do_not_accept_null(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        with pytest.raises(IntegrityError),db.begin_nested():
            db.add(JobInventoryReview(job_id=job.id,inventory_complete=True,
                o_applicability="not_applicable",o_reason=None,q_applicability="not_applicable",q_reason=None,
                source_fingerprint="0"*64,**MatchingInputsService.review(users[1],"approved")))
            db.flush()

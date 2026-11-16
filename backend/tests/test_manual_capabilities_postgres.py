"""Disposable PostgreSQL source/ownership/history/migration proofs."""
import json
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill, User
from app.db.models.explainable import (JobManualCapability, JobRequirementGroupMember, JobRequirementGroup,
    MatchingRun, JobMatchResult, SkillGapResult, SkillGapAtomicResult)
from app.matching.manual_capabilities import INPUT_ADAPTER_VERSION
from app.repositories.matching_inputs_repository import snapshot
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import TEMPLATE_V1, TEMPLATE_V2
from app.services.matching_inputs_service import MatchingInputsService
from app.services.matching_runs_service import MatchingRunsService
from test_manual_capabilities import setup, payload, manual_group
from test_matching_inputs import group_payload, sign_payload
from test_matching_inputs_postgres import run_result, legacy_snapshot
from test_matching_runs import seed_runs
from test_taxonomy_postgres import pg_database  # noqa: F401


def test_manual_write_preserves_every_legacy_table_and_retrieval_contract(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, skill, service = setup(db)
        # Real synthetic embeddings and legacy rows are covered by the existing
        # preservation helper; compare all non-Phase-6 tables byte-for-byte here.
        from app.db.models import CandidateProfileEmbedding, JobEmbedding, CandidateJobMatch
        metadata = dict(embedding=[1.0]+[0.0]*383, model_id="synthetic", model_revision="f"*40,
            template_version=TEMPLATE_V2, source_hash="1"*64, taxonomy_fingerprint="2"*64, status="ready")
        db.add_all([CandidateProfileEmbedding(candidate_profile_id=profiles[0].id, **metadata),
            JobEmbedding(job_id=job.id, **metadata), CandidateJobMatch(candidate_profile_id=profiles[0].id,
                job_id=job.id, score=77, matched_required=[], matched_preferred=[], missing_required=[],
                missing_preferred=[], candidate_skill_count=1, job_skill_count=1, explanation="synthetic")])
        db.commit()
        before = legacy_snapshot(engine)
        representations = [(RetrievalRepository(db, version).job_input(job).text,
                            RetrievalRepository(db, version).job_input(job).source_hash) for version in (TEMPLATE_V1, TEMPLATE_V2)]
        source = service.read_job(job.id)["source_fingerprint"]
        created = service.create_capability(users[1], job.id, payload(service, job))
        group = service.create_group(users[1], job.id, manual_group(service, job, created))
        service.create_group(users[1], job.id, group_payload(service.read_job(job.id), skill))
        service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
        assert service.read_job(job.id)["source_fingerprint"] == source
        assert [(RetrievalRepository(db, version).job_input(job).text,
                 RetrievalRepository(db, version).job_input(job).source_hash) for version in (TEMPLATE_V1, TEMPLATE_V2)] == representations
        service.delete_group(users[1], job.id, group["id"], service.read_job(job.id)["fingerprint"])
        service.delete_capability(users[1], job.id, created["id"], service.read_job(job.id)["fingerprint"])
    assert legacy_snapshot(engine) == before


def test_database_source_immutable_review_and_composite_ownership(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _, service = setup(db)
        created = service.create_capability(users[1], job.id, payload(service, job))
        cid, reviewer = created["id"], users[1].id
        for expression in ("raw_text='forged'", "reviewer_role_snapshot='forged'", "reviewed_by=NULL"):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(f"UPDATE job_manual_capabilities SET {expression} WHERE id=:id"), {"id": cid})
        original = db.get(JobManualCapability, cid)
        forged = snapshot(original) | {"id": uuid4(), "raw_text": "forged"}
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(JobManualCapability(**forged)); db.flush()
        db.delete(db.get(User, reviewer)); db.commit()
        db.refresh(original)
        assert original.reviewed_by is None and original.reviewer_pseudonym_snapshot == created["reviewer_pseudonym_snapshot"]
        other = Job(title="Other", description="Unrelated"); db.add(other); db.commit()
        with pytest.raises(Exception) as exc:
            service.create_group(users[2], other.id, manual_group(service, other, created))
        assert exc.value.status_code == 404
        group = service.create_group(users[2], job.id, manual_group(service, job, created))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(JobRequirementGroupMember(job_id=other.id, group_id=group["id"], manual_capability_id=cid))
            db.flush(); db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_grouped_delete_direct_final_member_and_job_cascade(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _, service = setup(db)
        created = service.create_capability(users[1], job.id, payload(service, job))
        group = service.create_group(users[1], job.id, manual_group(service, job, created))
        with pytest.raises(DBAPIError):
            db.delete(db.get(JobManualCapability, created["id"])); db.commit()
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM job_requirement_group_members WHERE group_id=:g"), {"g": group["id"]}); db.commit()
        db.rollback()
        db.delete(db.get(Job, job.id)); db.flush(); db.rollback()
        assert db.get(JobManualCapability, created["id"]) is not None
        db.delete(db.get(Job, job.id)); db.commit()
    with Session(engine) as db:
        assert db.get(JobManualCapability, created["id"]) is None
        assert db.get(JobRequirementGroup, group["id"]) is None


def test_scoped_invalidation_preserves_historical_snapshots_and_rollback(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, _, service = setup(db)
        old, old_result = run_result(db, profiles[0], job)
        old.is_current=False; old.status="historical"; db.commit()
        current, result = run_result(db, profiles[0], job); db.commit()
        other_job = Job(title="Unrelated", description="Separate synthetic source")
        db.add(other_job); db.commit()
        other, other_result = run_result(db, profiles[3], other_job); db.commit()
        before_other = snapshot(other), snapshot(other_result)
        before_old = snapshot(old), snapshot(old_result)
        before_current = snapshot(current), snapshot(result)
        def fail():
            db.flush(); raise RuntimeError("failure after invalidation")
        with monkeypatch.context() as patch:
            patch.setattr(service.repo, "finish", fail)
            with pytest.raises(RuntimeError): service.create_capability(users[1], job.id, payload(service, job))
        db.expire_all()
        assert (snapshot(current), snapshot(result)) == before_current
        service.create_capability(users[1], job.id, payload(service, job))
        db.expire_all()
        assert current.status == result.status == "stale"
        assert (snapshot(old), snapshot(old_result)) == before_old
        assert (snapshot(other), snapshot(other_result)) == before_other


def test_concurrent_expected_fingerprint_and_shared_gate(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _, service = setup(db)
        uid, jid = users[1].id, job.id
        proposed = payload(service, job)
        service.create_capability(users[1], job.id, proposed)
    with Session(engine) as db:
        with pytest.raises(Exception) as exc:
            MatchingInputsService(db).create_capability(db.get(User, uid), jid, proposed)
        assert exc.value.status_code == 409
    with engine.connect() as first, engine.connect() as second:
        first.execute(text("UPDATE job_manual_capabilities SET raw_text=raw_text WHERE false"))
        assert not second.scalar(text("SELECT pg_try_advisory_xact_lock(603402)"))
        first.rollback(); second.rollback()


@pytest.mark.parametrize("tag", ["matching_runs", "job_inventory_reviews", "manual"])
def test_safe_downgrade_refuses_version_tags_alone_or_manual_rows(pg_database, tag):
    engine, config, _ = pg_database
    with Session(engine) as db:
        users, profiles, job, skill, service = setup(db)
        if tag == "manual": service.create_capability(users[1], job.id, payload(service, job))
        elif tag == "matching_runs": run_result(db, profiles[0], job); db.commit()
        else:
            service.create_group(users[1], job.id, group_payload(service.read_job(job.id), skill))
            service.signoff(users[1], job.id, sign_payload(service.read_job(job.id)))
    with engine.connect() as conn:
        before = {table: [dict(x) for x in conn.execute(text(f"SELECT * FROM {table}")).mappings()]
                  for table in ("matching_runs", "job_inventory_reviews", "job_manual_capabilities")}
    with pytest.raises(DBAPIError, match="Downgrade refuses"):
        command.downgrade(config, "0010_matching_input_integrity")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0011_manual_job_capabilities"
        for table, rows in before.items():
            assert [dict(x) for x in conn.execute(text(f"SELECT * FROM {table}")).mappings()] == rows


def test_populated_0010_roundtrip_preserves_legacy_inputs(pg_database):
    engine, config, _ = pg_database
    command.downgrade(config, "0010_matching_input_integrity")
    with Session(engine) as db:
        from test_matching_inputs import seed
        seed(db)
    before = legacy_snapshot(engine)
    command.upgrade(config, "head")
    assert legacy_snapshot(engine) == before
    command.downgrade(config, "0010_matching_input_integrity")
    assert legacy_snapshot(engine) == before
    command.upgrade(config, "head")
    assert legacy_snapshot(engine) == before


def test_old_version_rows_remain_untouched_and_cannot_be_current(pg_database):
    from app.db.models.explainable import ScoringConfiguration
    from app.matching.policy import POLICY_HASH
    from test_matching_inputs import seed
    engine, config, _ = pg_database
    command.downgrade(config, "0010_matching_input_integrity")
    with Session(engine) as db:
        _, profiles, job, _ = seed(db)
        run_id, review_id, jid = uuid4(), uuid4(), job.id
        db.execute(text("""INSERT INTO matching_runs (id,candidate_profile_id,policy_id,
            candidate_fingerprint,policy_fingerprint,input_fingerprint,universe_fingerprint,
            status,is_current,pool_limit,stale_missing_job_count)
            VALUES (:id,:candidate,:policy,:hash,:policyhash,:hash,:hash,'current',true,20,0)"""),
            {"id":run_id,"candidate":profiles[0].id,"policy":db.scalar(select(ScoringConfiguration.id)),
             "hash":"1"*64,"policyhash":POLICY_HASH})
        db.execute(text("""INSERT INTO job_inventory_reviews (id,job_id,inventory_complete,
            o_applicability,o_reason,q_applicability,q_reason,source_fingerprint,
            review_status,reviewed_by,reviewer_pseudonym_snapshot,reviewer_role_snapshot,reviewed_at,evidence_snapshot)
            VALUES (:id,:job,true,'not_applicable','no_occupation_scope_stated','not_applicable',
            'no_qualification_or_experience_scope_stated',:hash,'approved',NULL,'synthetic_reviewer','researcher',now(),'{}')"""),
            {"id":review_id,"job":jid,"hash":"1"*64})
        db.commit()
    with engine.connect() as conn:
        before = {table: conn.execute(text(f"SELECT * FROM {table}")).mappings().one()
                  for table in ("matching_runs", "job_inventory_reviews")}
    command.upgrade(config, "head")
    with engine.connect() as conn:
        for table, old in before.items():
            after = conn.execute(text(f"SELECT * FROM {table}")).mappings().one()
            assert after["input_adapter_version"] is None
            assert dict(old) == {key: after[key] for key in old}
    with Session(engine) as db:
        assert not MatchingInputsService(db).read_job(jid)["inventory_current"]
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE matching_runs SET input_adapter_version=:v WHERE id=:id"),
                       {"v":INPUT_ADAPTER_VERSION,"id":run_id})
    # No new tags were written: retained old history supports safe round trips.
    command.downgrade(config, "0010_matching_input_integrity")
    command.upgrade(config, "head")


@pytest.mark.parametrize("component,classification,critical", [("Q","required",False), ("P","preferred",False), ("R","required",True)])
def test_database_manual_group_rules(pg_database, component, classification, critical):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _, service = setup(db)
        cap = service.create_capability(users[1], job.id, payload(service, job))
        with pytest.raises(DBAPIError):
            group = JobRequirementGroup(id=uuid4(), job_id=job.id, component=component,
                classification=classification, critical=critical, operator="SINGLE",
                source_fingerprint=service.read_job(job.id)["source_fingerprint"],
                **MatchingInputsService.review(users[1],"approved"))
            db.add(group); db.flush()
            db.add(JobRequirementGroupMember(job_id=job.id,group_id=group.id,manual_capability_id=cap["id"]))
            db.commit()
        db.rollback()


def test_direct_multi_member_removal_keeps_valid_manual_group(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, _, service = setup(db)
        caps = [service.create_capability(users[1],job.id,payload(service,job,name)) for name in ("Café","Git")]
        group = service.create_group(users[1],job.id,manual_group(service,job,caps[0],operator="AND",
            members=[{"manual_capability_id":cap["id"]} for cap in caps]))
        db.execute(text("DELETE FROM job_requirement_group_members WHERE manual_capability_id=:id"), {"id":caps[0]["id"]})
        db.commit()
        assert db.get(JobRequirementGroup,group["id"]) is not None
        assert len(list(db.scalars(select(JobRequirementGroupMember).where(JobRequirementGroupMember.group_id==group["id"]))))==1


def test_manual_result_anchors_survive_member_delete_then_job_erasure(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, _, job, skill = seed_runs(db)
        job.cleaned_description="Requires Git and Java"; db.commit()
        service=MatchingInputsService(db)
        old_group = service.read_job(job.id)["groups"][0]
        service.delete_group(users[1], job.id, old_group["id"], service.read_job(job.id)["fingerprint"])
        service.create_group(users[1], job.id, group_payload(service.read_job(job.id), skill))
        created=[]
        for name in ("Git", "Java"):
            cap=service.create_capability(users[1],job.id,payload(service,job,name))
            grp=service.create_group(users[1],job.id,manual_group(service,job,cap))
            created.append((cap,grp))
        service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        # Synthetic source edit requires a fresh ready vector, never inference.
        from app.retrieval.representation import DIMENSION
        retrieval=RetrievalRepository(db,TEMPLATE_V2)
        retrieval.upsert(job.id,"job",retrieval.job_input(job),[1.0]+[0.0]*(DIMENSION-1)); db.commit()
        response=MatchingRunsService(db).create(users[0]); rid=response["run_id"]
        result=db.scalar(select(JobMatchResult).where(JobMatchResult.run_id==rid))
        atoms=list(db.scalars(select(SkillGapAtomicResult).join(SkillGapResult).where(SkillGapResult.result_id==result.id)))
        manual_atoms=[x for x in atoms if x.reason_parameters.get("requirement_origin")=="phase6_manual_capability"]
        assert len(manual_atoms)==2 and len({x.occurrence_fingerprint for x in manual_atoms})==2
        before=[dict(x.reason_parameters) for x in manual_atoms]
        for cap,grp in created:
            service.delete_group(users[1],job.id,grp["id"],service.read_job(job.id)["fingerprint"])
            service.delete_capability(users[1],job.id,cap["id"],service.read_job(job.id)["fingerprint"])
        db.expire_all()
        assert all(x.member_id is None for x in manual_atoms)
        assert [x.reason_parameters for x in manual_atoms]==before
        assert len({x.occurrence_fingerprint for x in manual_atoms})==2
        db.delete(job); db.commit(); db.expire_all()
        assert all(x.reason_parameters=={} for x in manual_atoms)
        assert db.get(MatchingRun,rid).status=="unreplayable"
        assert result.job_id is None and result.alignment_fraction is not None

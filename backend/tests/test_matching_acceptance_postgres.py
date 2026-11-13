"""Database-authoritative correction regressions; disposable synthetic data only."""
import hashlib
import json
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select,text,delete
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CandidateProfile,CvDocument,Job,JobSkill
from app.db.models.explainable import (ScoringConfiguration,CandidateMatchingFact,JobMatchingFact,
    JobRequirementGroup,JobRequirementGroupMember,JobOccurrenceReview,JobInventoryReview,
    MatchingRun,JobMatchResult,MatchScoreComponent,SkillGapResult,SkillGapAtomicResult)
from app.matching.policy import CANONICAL_CONFIGURATION,POLICY_HASH
from app.repositories.document_repository import DocumentRepository
from app.repositories.matching_inputs_repository import MatchingInputsRepository,snapshot
from app.schemas.matching_inputs import FactInput,GroupInput,OccurrenceInput
from app.services.matching_inputs_service import MatchingInputsService
from test_matching_inputs import seed,group_payload,sign_payload
from test_matching_inputs_postgres import run_result,legacy_snapshot
from test_taxonomy_postgres import pg_database  # noqa: F401


def add_group(db,user,job,skills,operator="SINGLE",component="R"):
    service=MatchingInputsService(db)
    return service.create_group(user,job.id,GroupInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],
        component=component,operator=operator,classification="required",critical=False,review_status="approved",
        members=[{"job_skill_id":x.id} for x in skills]))


def test_reprocessing_removes_only_cascade_emptied_groups_and_invalidates_inventory(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db)
        retained=JobSkill(job_id=job.id,raw_text="Java",normalized_text="java",review_status="approved",requirement_type="required",source="manual_review")
        db.add(retained);db.commit()
        gone=add_group(db,users[1],job,[skill]);keep=add_group(db,users[1],job,[retained])
        service=MatchingInputsService(db);service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        before_keep=snapshot(db.get(JobRequirementGroup,keep["id"]))
        ids=job.id,gone["id"],keep["id"]
        DocumentRepository(db).replace_job_terms(job,[]);db.commit()
    with Session(engine) as db:
        assert db.get(JobRequirementGroup,ids[1]) is None
        assert snapshot(db.get(JobRequirementGroup,ids[2]))==before_keep
        state=MatchingInputsService(db).read_job(ids[0])
        assert not state["inventory_current"] and not state["inventory"]["inventory_complete"]


def test_direct_final_member_delete_and_empty_group_are_rejected(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db);group=add_group(db,users[1],job,[skill])
        member=db.scalar(select(JobRequirementGroupMember).where(JobRequirementGroupMember.group_id==group["id"]))
        with pytest.raises(DBAPIError):
            db.delete(member);db.commit()
        db.rollback()
        assert db.get(JobRequirementGroup,group["id"]) is not None
        assert db.get(JobSkill,skill.id) is not None


@pytest.mark.parametrize("source_deleted",[True,False])
def test_multi_member_group_survives_single_member_removal(pg_database,source_deleted):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db)
        second=JobSkill(job_id=job.id,raw_text="Java",normalized_text="java",review_status="approved",requirement_type="required")
        db.add(second);db.commit()
        group=add_group(db,users[1],job,[skill,second],"AND")
        member=db.scalar(select(JobRequirementGroupMember).where(JobRequirementGroupMember.job_skill_id==skill.id))
        db.delete(skill if source_deleted else member);db.commit()
        assert db.get(JobRequirementGroup,group["id"]) is not None
        assert len(list(db.scalars(select(JobRequirementGroupMember).where(JobRequirementGroupMember.group_id==group["id"]))))==1


def test_reprocessing_rollback_restores_group_members_and_signoff(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db);group=add_group(db,users[1],job,[skill])
        service=MatchingInputsService(db);service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        before=service.read_job(job.id);jid=job.id
        DocumentRepository(db).replace_job_terms(job,[])
        db.rollback()
    with Session(engine) as db:
        assert MatchingInputsService(db).read_job(jid)==before


def test_q_fact_cascade_deletes_its_empty_group(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,_=seed(db);service=MatchingInputsService(db)
        fact=service.create_fact(users[1],FactInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],
            fact_type="qualification",statement="Degree requirement",completion="completed",evidence_reference="line 1",review_status="approved"),job.id)
        group=service.create_group(users[1],job.id,GroupInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],
            component="Q",operator="SINGLE",classification="required",critical=False,review_status="approved",
            members=[{"job_matching_fact_id":fact["id"]}]))
        db.delete(db.get(JobMatchingFact,fact["id"]));db.commit()
        assert db.get(JobRequirementGroup,group["id"]) is None


@pytest.mark.parametrize("operation",["UPDATE scoring_configurations SET engine_version='changed'",
                                    "DELETE FROM scoring_configurations","TRUNCATE scoring_configurations CASCADE"])
def test_policy_update_delete_truncate_are_blocked(pg_database,operation):
    engine,_,_=pg_database
    with engine.connect() as conn:
        with pytest.raises(DBAPIError,match="immutable"): conn.execute(text(operation))
        conn.rollback()
        row=conn.execute(text("SELECT canonical_json,policy_hash FROM scoring_configurations")).one()
        assert tuple(row)==(CANONICAL_CONFIGURATION,POLICY_HASH)


@pytest.mark.parametrize("case",["arbitrary","incorrect_hash","nonempty_v1","changed_v1"])
def test_policy_insert_guard_rejects_invalid_content(pg_database,case):
    engine,_,_=pg_database
    version="future-test-only";body={"policy_version":version};engine_version="test-only"
    if case=="arbitrary": body={"arbitrary":"not a policy"}
    if case in {"nonempty_v1","changed_v1"}:
        version="matching-policy-v1";body=json.loads(CANONICAL_CONFIGURATION);engine_version=version
        if case=="nonempty_v1": body["relationship_allowlist"]=["broader"]
        else: body["dense_numeric_weight"]=1
    canonical=json.dumps(body,sort_keys=True,separators=(",",":"))
    checksum="0"*64 if case=="incorrect_hash" else hashlib.sha256(canonical.encode()).hexdigest()
    with engine.connect() as conn:
        with pytest.raises(DBAPIError,match="Invalid.*policy"):
            conn.execute(text("INSERT INTO scoring_configurations VALUES (:id,:version,:canonical,:hash,:engine)"),
                dict(id=uuid4(),version=version,canonical=canonical,hash=checksum,engine=engine_version))
        conn.rollback()


def test_future_immutable_policy_preserves_exact_utf8_bytes(pg_database):
    engine,_,_=pg_database
    canonical=json.dumps({"policy_version":"future-test-only","note":"\u00e9"},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    checksum=hashlib.sha256(canonical.encode("utf8")).hexdigest()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO scoring_configurations VALUES (:id,:v,:c,:h,:e)"),
                     dict(id=uuid4(),v="future-test-only",c=canonical,h=checksum,e="future-test-only"))
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT canonical_json FROM scoring_configurations WHERE version='future-test-only'"))==canonical


@pytest.mark.parametrize("exact,numeric,valid",[("0/1",0,True),("1/1",1,True),("1/3",Decimal(".333333"),True),
    (None,None,True),(None,0,False),("1/0",0,False),("1",1,False),("2/2",1,False),
    ("01/2",Decimal(".5"),False),("-0/1",0,False),("1/3",Decimal(".333334"),False),
    ("-1/2",Decimal("-.5"),False),("2/1",2,False)])
def test_gap_fraction_range_and_projection_constraints(pg_database,exact,numeric,valid):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,skill=seed(db);run,result=run_result(db,profiles[0],job)
        gap=SkillGapResult(result_id=result.id,group_id=None,support_fraction=exact,support_value=numeric,
                           critical=False,status="unassessed" if exact is None else "Missing",reason_code="test",reason_parameters={},evidence_snapshot={})
        db.add(gap)
        if valid: db.commit()
        else:
            with pytest.raises(IntegrityError): db.flush()
            db.rollback()


@pytest.mark.parametrize("provisional,exact,value,valid",[(False,None,None,False),(True,"1/1",1,False),
    (True,None,None,True),(False,"100/1",100,True),(False,"101/1",101,False),(False,"1/3",Decimal(".333334"),False)])
def test_result_provisional_equivalence_and_alignment_constraints(pg_database,provisional,exact,value,valid):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,_=seed(db);run,result=run_result(db,profiles[0],job);db.commit()
        result.provisional=provisional;result.alignment_fraction=exact;result.alignment_value=value
        if valid: db.commit()
        else:
            with pytest.raises(IntegrityError): db.flush()
            db.rollback()


@pytest.mark.parametrize("target",["component","weight","atomic"])
@pytest.mark.parametrize("exact,value,valid",[(None,None,True),("0/1",0,True),("1/1",1,True),
    ("1/3",Decimal(".333334"),False),("2/1",2,False),("-1/1",-1,False),("1/0",0,False)])
def test_component_weight_and_atomic_support_constraints(pg_database,target,exact,value,valid):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,_=seed(db);run,result=run_result(db,profiles[0],job)
        if target=="atomic":
            gap=SkillGapResult(result_id=result.id,group_id=None,support_fraction=None,support_value=None,
                critical=False,status="unassessed",reason_code="unknown",reason_parameters={},evidence_snapshot={})
            db.add(gap);db.flush()
            row=SkillGapAtomicResult(gap_id=gap.id,member_id=None,occurrence_fingerprint="0"*64,
                support_fraction=exact,support_value=value,reason_code="test",reason_parameters={})
        else:
            row=MatchScoreComponent(result_id=result.id,component="R",status="assessed",applicability="applicable",
                numerator=1,denominator=1,base_weight=7,effective_weight_fraction="1/1",effective_weight_value=1,
                value_fraction="1/1",value=1,reason_code="test",reason_parameters={})
            if target=="component":
                row.value_fraction=exact;row.value=value
                row.numerator=int(exact.split('/')[0]) if exact else None
                row.denominator=int(exact.split('/')[1]) if exact else None
            else: row.effective_weight_fraction=exact;row.effective_weight_value=value
        db.add(row)
        if valid: db.commit()
        else:
            with pytest.raises(IntegrityError): db.flush()
            db.rollback()


def test_historical_results_unchanged_by_current_invalidation(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,_=seed(db)
        old,old_result=run_result(db,profiles[0],job);old.status="historical";old.is_current=False;db.commit()
        current,current_result=run_result(db,profiles[0],job);db.commit()
        before=snapshot(old),snapshot(old_result);ids=old.id,old_result.id,current.id,current_result.id
        MatchingInputsRepository(db).invalidate_job(job.id);db.commit()
    with Session(engine) as db:
        assert (snapshot(db.get(MatchingRun,ids[0])),snapshot(db.get(JobMatchResult,ids[1])))==before
        assert db.get(MatchingRun,ids[2]).status=="stale"
        assert db.get(JobMatchResult,ids[3]).status=="stale"


def test_override_must_be_explicit_reviewed_and_source_current(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db);skill.requirement_type="unknown";db.commit()
        group=add_group(db,users[1],job,[skill]);service=MatchingInputsService(db)
        with pytest.raises(HTTPException): service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        review=service.classify(users[1],job.id,skill.id,OccurrenceInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],
            classification="required",review_status="approved",reason="Explicit requirement in source line 1"))
        assert review["reason"] and review["reviewed_at"] and review["reviewer_pseudonym_snapshot"]
        service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
        job.description="Changed source requirements";db.commit()
        service.delete_group(users[1],job.id,group["id"],service.read_job(job.id)["fingerprint"])
        add_group(db,users[1],job,[skill])
        with pytest.raises(HTTPException,match="stale occurrence"):
            service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))


def test_cross_job_occurrence_review_and_member_foreign_keys(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db);group=add_group(db,users[1],job,[skill])
        other=Job(title="Other synthetic",description="Other synthetic source");db.add(other);db.flush()
        second=JobSkill(job_id=other.id,raw_text="Java",normalized_text="java",review_status="approved",requirement_type="required")
        db.add(second);db.commit()
        with pytest.raises(IntegrityError),db.begin_nested():
            db.add(JobOccurrenceReview(job_id=job.id,job_skill_id=second.id,classification="required",reason="source",
                source_fingerprint="0"*64,**MatchingInputsService.review(users[1],"approved")));db.flush()
        with pytest.raises(IntegrityError),db.begin_nested():
            db.add(JobRequirementGroupMember(group_id=group["id"],job_id=job.id,job_skill_id=second.id));db.flush()
        assert db.get(JobSkill,second.id).job_id==other.id


def test_cross_job_q_fact_member_and_api_classification_are_rejected(pg_database):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,_,job,skill=seed(db);service=MatchingInputsService(db)
        other=Job(title="Other Q scope",description="Other source");db.add(other);db.commit()
        fact=service.create_fact(users[1],FactInput(expected_fingerprint=service.read_job(other.id)["fingerprint"],
            fact_type="qualification",statement="Degree",completion="completed",evidence_reference="line 1",review_status="approved"),other.id)
        with pytest.raises(HTTPException) as exc:
            service.create_group(users[1],job.id,GroupInput(expected_fingerprint=service.read_job(job.id)["fingerprint"],
                component="Q",operator="SINGLE",classification="required",critical=False,review_status="approved",
                members=[{"job_matching_fact_id":fact["id"]}]))
        assert exc.value.status_code==404
        qgroup=service.create_group(users[1],other.id,GroupInput(expected_fingerprint=service.read_job(other.id)["fingerprint"],
            component="Q",operator="SINGLE",classification="required",critical=False,review_status="approved",
            members=[{"job_matching_fact_id":fact["id"]}]))
        with pytest.raises(IntegrityError),db.begin_nested():
            db.execute(text("UPDATE job_requirement_group_members SET job_id=:job WHERE group_id=:group"),
                       {"job":job.id,"group":qgroup["id"]})
        with pytest.raises(HTTPException) as exc:
            service.classify(users[1],other.id,skill.id,OccurrenceInput(expected_fingerprint=service.read_job(other.id)["fingerprint"],
                classification="required",review_status="approved",reason="Source review"))
        assert exc.value.status_code==404


@pytest.mark.parametrize("target",["cv","fact","profile"])
@pytest.mark.parametrize("rollback",[False,True])
def test_candidate_source_erasure_and_rollback_preserve_unrelated_arithmetic(pg_database,target,rollback):
    engine,_,_=pg_database
    with Session(engine) as db:
        users,profiles,job,_=seed(db)
        cv=CvDocument(candidate_profile_id=profiles[0].id,content_type="text/plain",source="synthetic",raw_text="Synthetic source document")
        db.add(cv);db.commit()
        service=MatchingInputsService(db)
        fact=service.create_fact(users[0],FactInput(expected_fingerprint=service.read_candidate(users[0])["fingerprint"],
            fact_type="experience",statement="Candidate-confirmed supervised practice",completion="unknown",
            cv_document_id=cv.id,evidence_reference="source line",review_status="approved"))
        run,result=run_result(db,profiles[0],job)
        result.reason_parameters={"candidate_evidence":"sensitive synthetic evidence sentinel"}
        gap=SkillGapResult(result_id=result.id,group_id=None,support_fraction="1/1",support_value=1,critical=False,
            status="Matched",reason_code="test",reason_parameters={"evidence":"sensitive synthetic evidence sentinel"},
            evidence_snapshot={"candidate_confirmed_evidence":"sensitive synthetic evidence sentinel"})
        db.add(gap);db.flush()
        component=MatchScoreComponent(result_id=result.id,component="R",status="assessed",applicability="applicable",
            numerator=1,denominator=1,base_weight=7,effective_weight_fraction="1/1",effective_weight_value=1,
            value_fraction="1/1",value=1,reason_code="test",reason_parameters={"evidence":"sensitive synthetic evidence sentinel"})
        atomic=SkillGapAtomicResult(gap_id=gap.id,member_id=None,occurrence_fingerprint="0"*64,
            support_fraction="1/1",support_value=1,reason_code="test",reason_parameters={"evidence":"sensitive synthetic evidence sentinel"})
        db.add_all([component,atomic]);db.flush()
        other,other_result=run_result(db,profiles[3],job);db.commit()
        ids=run.id,result.id,gap.id,other.id,other_result.id,component.id,atomic.id
        before=snapshot(run),snapshot(result),snapshot(gap),snapshot(component),snapshot(atomic)
        unrelated=snapshot(other),snapshot(other_result),snapshot(job),snapshot(db.scalar(select(ScoringConfiguration)))
        item=cv if target=="cv" else db.get(CandidateMatchingFact,fact["id"]) if target=="fact" else profiles[0]
        db.delete(item);db.flush()
        if rollback: db.rollback()
        else: db.commit()
    with Session(engine) as db:
        run=db.get(MatchingRun,ids[0]);result=db.get(JobMatchResult,ids[1]);gap=db.get(SkillGapResult,ids[2])
        component=db.get(MatchScoreComponent,ids[5]);atomic=db.get(SkillGapAtomicResult,ids[6])
        if rollback:
            assert (snapshot(run),snapshot(result),snapshot(gap),snapshot(component),snapshot(atomic))==before
        else:
            assert run.status=="unreplayable" and not run.is_current
            assert result.status=="unreplayable" and result.reason_parameters=={}
            assert gap.evidence_snapshot=={} and gap.reason_parameters=={}
            assert component.reason_parameters=={} and atomic.reason_parameters=={}
            assert component.value_fraction=="1/1" and atomic.support_fraction=="1/1"
            assert result.alignment_fraction=="100/1" and result.alignment_value==100
            if target=="profile": assert run.candidate_profile_id is None
        assert (snapshot(db.get(MatchingRun,ids[3])),snapshot(db.get(JobMatchResult,ids[4])),
                snapshot(db.get(Job,result.job_id)),snapshot(db.scalar(select(ScoringConfiguration))))==unrelated

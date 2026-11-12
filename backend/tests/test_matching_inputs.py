from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import get_current_user
from app.db.models import User,Role,CandidateProfile,Job,JobSkill
from app.db.models.explainable import CandidateMatchingFact,JobRequirementGroup,JobInventoryReview,MatchingRun
from app.db.session import get_db
from app.main import create_app
from app.schemas.matching_inputs import FactInput,GroupInput,InventoryInput,OccurrenceInput
from app.services.matching_inputs_service import MatchingInputsService


def seed(db):
    from app.core.config import settings
    def role(name):
        return db.scalar(select(Role).where(Role.name==name)) or Role(name=name,description="")
    candidate,admin,researcher=role("candidate"),role(settings.ADMIN_ROLE),role("researcher")
    users=[User(email=f"{uuid4()}@example.test",full_name="Synthetic",hashed_password="unused",roles=roles)
           for roles in ([candidate],[admin,candidate],[researcher,candidate],[candidate])]
    db.add_all(users)
    db.flush()
    profiles=[CandidateProfile(user_id=x.id) for x in users]
    job=Job(title="Synthetic engineering",description="Requires Python",status="processed")
    db.add_all([*profiles,job]); db.flush()
    skill=JobSkill(job_id=job.id,raw_text="Python",normalized_text="python",skill_type="skill",
                   review_status="approved",requirement_type="required")
    db.add(skill); db.commit()
    return users,profiles,job,skill


def test_candidate_facts_ownership_and_no_protected_fields(db_session):
    users,profiles,job,skill=seed(db_session)
    service=MatchingInputsService(db_session)
    before=service.read_candidate(users[0])
    payload=FactInput(expected_fingerprint=before["fingerprint"],fact_type="qualification",statement="Degree in progress",
                      completion="in_progress",evidence_reference="approved occurrence",review_status="approved")
    created=service.create_fact(users[0],payload)
    assert created["provenance"] == "candidate_confirmed"
    assert service.read_candidate(users[3])["facts"] == []
    with pytest.raises(HTTPException) as exc: service.delete_fact(users[3],created["id"],service.read_candidate(users[3])["fingerprint"])
    assert exc.value.status_code==404
    with pytest.raises(ValueError): FactInput(**payload.model_dump(), citizenship="x")


def group_payload(state,skill):
    return GroupInput(expected_fingerprint=state["fingerprint"],component="R",operator="SINGLE",
                      classification="required",critical=False,review_status="approved",members=[{"job_skill_id":skill.id}])


def sign_payload(state,**extra):
    values=dict(expected_fingerprint=state["fingerprint"],review_status="approved",inventory_complete=True,
                o_applicability="not_applicable",o_reason="no_occupation_scope_stated",
                q_applicability="not_applicable",q_reason="no_qualification_or_experience_scope_stated")
    values.update(extra)
    return InventoryInput(**values)


def test_inventory_explicit_complete_noop_and_get_no_write(db_session):
    users,profiles,job,skill=seed(db_session)
    service=MatchingInputsService(db_session)
    initial=service.read_job(job.id)
    with pytest.raises(HTTPException): service.signoff(users[1],job.id,sign_payload(initial))
    service.create_group(users[1],job.id,group_payload(service.read_job(job.id),skill))
    state=service.read_job(job.id)
    result=service.signoff(users[1],job.id,sign_payload(state))
    assert service.read_job(job.id)["inventory_current"]
    repeated=service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
    assert repeated==result
    assert len(list(db_session.scalars(select(JobInventoryReview))))==1
    assert not db_session.new and not db_session.dirty


@pytest.mark.parametrize("status,classification,kind",[("pending","required","skill"),("approved","unknown","skill"),
                                                       ("approved","required","qualification")])
def test_signoff_blocks_unresolved_bound_occurrences(db_session,status,classification,kind):
    users,profiles,job,skill=seed(db_session)
    skill.review_status=status;skill.requirement_type=classification;skill.skill_type=kind;db_session.commit()
    service=MatchingInputsService(db_session)
    with pytest.raises(HTTPException): service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))


def test_inventory_non_requirement_is_explicit_and_does_not_rewrite_jobskill(db_session):
    users,profiles,job,skill=seed(db_session)
    service=MatchingInputsService(db_session)
    state=service.read_job(job.id)
    service.classify(users[1],job.id,skill.id,OccurrenceInput(expected_fingerprint=state["fingerprint"],classification="non_requirement",review_status="approved",reason="Reviewed as page noise"))
    service.signoff(users[1],job.id,sign_payload(service.read_job(job.id)))
    db_session.refresh(skill)
    assert skill.requirement_type=="required" and skill.review_status=="approved"


def test_input_transaction_failure_rolls_back(db_session,monkeypatch):
    users,profiles,job,skill=seed(db_session)
    service=MatchingInputsService(db_session)
    before=service.read_job(job.id)
    def fail():
        db_session.flush()
        raise RuntimeError("before commit")
    monkeypatch.setattr(service.repo,"finish",fail)
    with pytest.raises(RuntimeError): service.create_group(users[1],job.id,group_payload(before,skill))
    assert service.read_job(job.id)==before


@pytest.mark.parametrize("model,values",[(FactInput,dict(fact_type="age",statement="x",completion="unknown",evidence_reference="x",review_status="approved")),
                                        (InventoryInput,dict(review_status="Approved",inventory_complete=False,o_applicability="unknown",q_applicability="unknown")),
                                        (OccurrenceInput,dict(classification="mandatory",review_status="approved"))])
def test_contract_rejects_noncanonical_values(model,values):
    with pytest.raises(ValueError): model(expected_fingerprint="0"*64,**values)


def test_input_api_role_matrix_and_ownership(db_session):
    users,profiles,job,skill=seed(db_session)
    app=create_app();app.dependency_overrides[get_db]=lambda:db_session
    with TestClient(app) as client:
        path=f"/matching-inputs/jobs/{job.id}/inventory"
        assert client.get(path).status_code==401
        for index,expected in [(0,403),(1,200),(2,200)]:
            app.dependency_overrides[get_current_user]=lambda index=index:users[index]
            assert client.get(path).status_code==expected
            payload=sign_payload(MatchingInputsService(db_session).read_job(job.id),inventory_complete=False,
                                 o_applicability="unknown",o_reason=None,q_applicability="unknown",q_reason=None)
            assert client.put(path,json=payload.model_dump()).status_code==expected
        app.dependency_overrides[get_current_user]=lambda:users[0]
        assert client.get(f"/matching-inputs/candidates/{profiles[3].id}/facts").status_code==404
        assert client.get(f"/matching-inputs/candidates/{profiles[0].id}/facts").status_code==200


def test_stale_fingerprint_rejected_and_get_detects_source_changes(db_session):
    users,profiles,job,skill=seed(db_session)
    service=MatchingInputsService(db_session)
    before=service.read_job(job.id)
    job.description="Changed duties";db_session.commit()
    with pytest.raises(HTTPException) as exc: service.create_group(users[1],job.id,group_payload(before,skill))
    assert exc.value.status_code==409
    assert not service.read_job(job.id)["inventory_current"]


@pytest.mark.parametrize("o,q",[("unknown","unknown"),("not_applicable","unknown"),("applicable","not_applicable")])
def test_applicability_requires_explicit_fixed_reasons(o,q):
    with pytest.raises(ValueError):
        InventoryInput(expected_fingerprint="0"*64,review_status="approved",inventory_complete=True,
                       o_applicability=o,q_applicability=q)


def test_all_reviewed_input_mutations_authoritative_role_guards(db_session):
    users,profiles,job,skill=seed(db_session)
    app=create_app();app.dependency_overrides[get_db]=lambda:db_session
    requests=[("post",f"/matching-inputs/jobs/{job.id}/facts"),
              ("post",f"/matching-inputs/jobs/{job.id}/groups"),
              ("delete",f"/matching-inputs/jobs/{job.id}/groups/{uuid4()}?expected_fingerprint={'0'*64}"),
              ("delete",f"/matching-inputs/jobs/{job.id}/facts/{uuid4()}?expected_fingerprint={'0'*64}"),
              ("put",f"/matching-inputs/jobs/{job.id}/occurrences/{skill.id}"),
              ("put",f"/matching-inputs/jobs/{job.id}/inventory")]
    with TestClient(app) as client:
        for method,path in requests:
            assert getattr(client,method)(path).status_code==401
        app.dependency_overrides[get_current_user]=lambda:users[0]
        for method,path in requests:
            assert getattr(client,method)(path).status_code==403
        for user in (users[1],users[2]):
            app.dependency_overrides[get_current_user]=lambda:user
            for method,path in requests:
                assert getattr(client,method)(path).status_code not in {401,403}
        app.dependency_overrides[get_current_user]=lambda:users[0]
        for method,path in [("post",f"/matching-inputs/candidates/{profiles[3].id}/facts"),
                            ("delete",f"/matching-inputs/candidates/{profiles[3].id}/facts/{uuid4()}?expected_fingerprint={'0'*64}")]:
            kwargs={"json":{"expected_fingerprint":"0"*64,"fact_type":"experience","statement":"Scope",
                            "completion":"unknown","evidence_reference":"line 1","review_status":"approved"}} if method=="post" else {}
            assert getattr(client,method)(path,**kwargs).status_code==404

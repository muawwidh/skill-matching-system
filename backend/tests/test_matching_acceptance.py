"""Acceptance corrections: exact arithmetic, evidence identity and participation."""
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction as F

import pytest
from fastapi import HTTPException

from app.matching.policy import (Component, Link, Occurrence, assess, group_support, identity,
    occupational_group, validate_fraction_pair)
from app.schemas.matching_inputs import FactInput, PolicyAssessmentInput
from app.services.matching_inputs_service import MatchingInputsService
from test_matching_inputs import seed
from test_matching_policy import components


@pytest.mark.parametrize("left,right",[("rejected","rejected"),("pending","pending"),("rejected","pending")])
def test_unapproved_links_never_block_text_only(left,right):
    candidate=Occurrence("c","Python","skill",links=(Link("old-a","a",left),))
    requirement=Occurrence("r","python","tool",links=(Link("old-b","b",right),))
    assert identity(candidate,requirement,frozenset({"current"})).reason=="text_only_match"


@pytest.mark.parametrize("selected",[frozenset(),frozenset({"a","b"})])
def test_approved_conflicts_cannot_be_erased_by_equal_text(selected):
    candidate=Occurrence("c","Python","skill",links=(Link("a","x"),))
    requirement=Occurrence("r","Python","skill",links=(Link("b","x"),))
    assert identity(candidate,requirement,selected).reason=="identity_incomparable"
    requirement=replace(requirement,links=(Link("a","y"),))
    reason="identity_mismatch" if "a" in selected else "identity_incomparable"
    assert identity(candidate,requirement,selected).reason==reason


@pytest.mark.parametrize("first,second,kind",[("Python","  pYtHoN\t","tool"),("Caf\u00e9","CAFE\u0301","skill")])
def test_unlinked_occurrence_deduplication_by_family_and_normalized_text(first,second,kind):
    requirements=(Occurrence("r1",first,"skill"),Occurrence("r2",second,kind),Occurrence("r3","Java","skill"))
    result=occupational_group("AND",requirements,(Occurrence("c",first,"skill"),),frozenset())
    assert result["support"]==F(1,2)
    assert len(result["assessments"])==3
    assert {x["requirement_id"] for x in result["assessments"]}=={"r1","r2","r3"}


def test_same_text_in_incompatible_families_is_not_deduplicated():
    result=occupational_group("AND",(Occurrence("r1","English","skill"),Occurrence("r2","English","language")),
                             (Occurrence("c","English","language"),),frozenset())
    assert result["support"]==F(1,2)


def test_exact_thirds_and_all_intermediate_values_remain_fraction():
    result=group_support("AND",[1,0,0])
    assert result==F(1,3) and type(result) is F
    value=assess(components(),inventory_complete=True,current=True,critical=(F(0),))
    assert type(value["alignment"]) is F
    assert type(value["critical_missing_support"]) is F
    for row in value["components"]:
        for field in ("coverage","value","effective_weight","contribution"):
            assert row[field] is None or type(row[field]) is F
    assert value["exact_fraction"]=="720/13"
    with pytest.raises(ValueError): group_support("AND",[1.0,0,0])


@pytest.mark.parametrize("applicability,groups",[("not_applicable",()),("unknown",()),("applicable",())])
def test_critical_inputs_require_nonempty_applicable_R_engine_and_schema(applicability,groups):
    values=list(components());values[0]=Component("R",applicability,groups)
    with pytest.raises(ValueError): assess(tuple(values),inventory_complete=True,current=True,critical=(F(0),))
    with pytest.raises(ValueError):
        PolicyAssessmentInput(components=[{"name":x.name,"applicability":x.applicability,"groups":list(x.groups)} for x in values],critical=[F(0)])


@pytest.mark.parametrize("exact,numeric,valid",[("0/1",Decimal(0),True),("1/3",Decimal(".333333"),True),
    (None,None,True),(None,Decimal(0),False),("1",Decimal(1),False),("2/2",Decimal(1),False),
    ("1/0",Decimal(0),False),("-0/1",Decimal(0),False),("01/2",Decimal(".5"),False),
    ("1/3",Decimal(".333334"),False)])
def test_canonical_fraction_projection_contract(exact,numeric,valid):
    assert validate_fraction_pair(exact,numeric) is valid


@pytest.mark.parametrize("status,allowed",[("active",True),("inactive",False),("deleted",False)])
def test_candidate_fact_participation_uses_active_profile_not_cv_consent(db_session,status,allowed):
    users,profiles,_,_=seed(db_session)
    profile=profiles[0];profile.status=status;profile.consent_to_process_cv=False;db_session.commit()
    service=MatchingInputsService(db_session)
    payload=FactInput(expected_fingerprint=service.read_candidate(users[0])["fingerprint"],fact_type="experience",
        statement="Candidate-confirmed supervised practice",completion="unknown",evidence_reference="manual confirmation",review_status="approved")
    if allowed:
        assert service.create_fact(users[0],payload)["provenance"]=="candidate_confirmed"
    else:
        with pytest.raises(HTTPException) as exc: service.create_fact(users[0],payload)
        assert exc.value.status_code==409


def test_deleted_profile_has_no_fact_target(db_session):
    users,profiles,_,_=seed(db_session)
    db_session.delete(profiles[0]);db_session.commit()
    with pytest.raises(HTTPException) as exc: MatchingInputsService(db_session).read_candidate(users[0])
    assert exc.value.status_code==404

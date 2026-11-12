import json
from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.matching.policy import (CANONICAL_CONFIGURATION, POLICY_HASH, Component, Link,
    Occurrence, assess, decimal_value, fingerprint, group_support, identity, normalize,
    requirement_support, tie_key, validate_configuration, occupational_group, support_explanation)


def components():
    return (Component("R", "applicable", (F(1), F(0))), Component("P", "applicable", (F(1),)),
            Component("O", "applicable", (F(1),)), Component("Q", "applicable", (F(0),)))


def test_exact_weights_fraction_and_deterministic_configuration():
    result = assess(components(), inventory_complete=True, current=True)
    assert result["alignment"] == F(850, 13)
    assert result["exact_fraction"] == "850/13"
    assert result["display"] == "65.38"
    assert [x["effective_weight"] for x in result["components"]] == [F(7,13), F(3,13), F(2,13), F(1,13)]
    assert POLICY_HASH == fingerprint(json.loads(CANONICAL_CONFIGURATION))
    validate_configuration(CANONICAL_CONFIGURATION)


@pytest.mark.parametrize("value,expected", [(F(1005,1000), "1.01"), (F(1004,1000), "1.00"), (F(2675,1000), "2.68")])
def test_half_up_without_storage_double_rounding(value, expected):
    assert str(decimal_value(value, 2)) == expected


@pytest.mark.parametrize("operator,values,expected", [
    ("SINGLE", (F(1),), F(1)), ("OR", (F(1),None), F(1)),
    ("OR", (F(0),None), None), ("AND", (F(1),None), None),
    ("AND", (F(1),F(0)), F(1,2)), ("OR", (F(0),F(0)), F(0))])
def test_one_level_group_unknown_arithmetic(operator, values, expected):
    assert group_support(operator, tuple((str(i), x) for i,x in enumerate(values))) == expected


def test_member_deduplication_and_invalid_groups():
    assert group_support("AND", (("a", F(1)), ("a", F(1)), ("b", F(0)))) == F(1,2)
    for operator, members in [("OR", ()), ("NESTED", (("a",F(1)),)),
                              ("SINGLE", (("a",F(1)),("b",F(0)))),
                              ("AND", (("a",F(1)),("a",F(0))))]:
        with pytest.raises(ValueError):
            group_support(operator, members)


@pytest.mark.parametrize("left,right,selected,reason,value", [
    ((Link("r","a"),),(Link("r","a"),),frozenset({"r"}),"identity_match",1),
    ((Link("r","a"),),(Link("r","b"),),frozenset({"r"}),"identity_mismatch",0),
    ((Link("r","a"),),(),frozenset({"r"}),"identity_incomparable",0),
    ((Link("r","a"),),(Link("s","a"),),frozenset({"r","s"}),"identity_incomparable",0),
    ((),(),frozenset(),"text_only_match",1),
])
def test_taxonomy_identity_and_conflicting_text(left, right, selected, reason, value):
    result = identity(Occurrence("c","Python","skill",links=left), Occurrence("j","Python","tool",links=right), selected)
    assert (result.reason,result.value) == (reason,F(value))


@pytest.mark.parametrize("left,right,kind,other,match", [
    ("  PYTHON\t", "python", "skill", "tool",True),
    ("Cafe\u0301", "CAFÉ", "domain_knowledge", "domain_knowledge",True),
    ("C++", "C", "skill", "skill",False),
    ("Python.org", "Python", "tool", "tool",False),
    ("English", "English", "language", "domain_knowledge",False),
    ("degree", "degree", "qualification", "qualification",False),
    ("5 years", "5 years", "experience", "experience",False),
])
def test_conservative_text_only_family_rules(left,right,kind,other,match):
    assert bool(identity(Occurrence("c",left,kind),Occurrence("j",right,other),frozenset()).value) == match


def test_occurrence_maximum_approved_only_and_order_independence():
    req = Occurrence("j","Python","skill",links=(Link("r","x"),))
    candidates = (Occurrence("a","Python","tool"), Occurrence("z","alias","skill",links=(Link("r","x"),)),
                  Occurrence("p","Python","skill",review_status="pending"))
    best, all_rows = requirement_support(candidates,req,frozenset({"r"}))
    assert best.reason == "identity_match" and best.value == 1
    assert len(all_rows) == 2 and all_rows[0].reason == "identity_incomparable"
    assert requirement_support(tuple(reversed(candidates)),req,frozenset({"r"})) == (best,all_rows)
    assert requirement_support((candidates[2],),req,frozenset({"r"}))[0].reason == "not_evidenced"


def test_incomparable_warns_but_does_not_make_known_zero_unknown():
    support = identity(Occurrence("c","Python","skill"),Occurrence("j","Python","skill",links=(Link("r","x"),)),frozenset({"r"}))
    assert support.reason == "identity_incomparable" and support.value == 0
    values = list(components())
    values[0] = Component("R","applicable",(support.value,))
    assert not assess(tuple(values),inventory_complete=True,current=True)["provisional"]


def test_empty_allowlist_and_full_configuration_are_enforced():
    for key,value in [("relationship_allowlist",["broader"]),("dense_numeric_weight",.35)]:
        config=json.loads(CANONICAL_CONFIGURATION)
        config[key]=value
        with pytest.raises(ValueError):
            validate_configuration(json.dumps(config))


def test_critical_maximum_is_not_diluted_by_satisfied_groups():
    base=assess(components(),inventory_complete=True,current=True,critical=(F(0),))
    extended=assess(components(),inventory_complete=True,current=True,critical=(F(0),F(1),F(1)))
    assert base["alignment"] == extended["alignment"] == F(850,13)-10
    assert assess(components(),inventory_complete=True,current=True)["critical_missing_support"] == 0
    assert assess(components(),inventory_complete=True,current=True,critical=(None,))["alignment"] is None


@pytest.mark.parametrize("change,reason", [("unknown","applicability_unknown"),("support","assessment_incomplete"),
                                            ("inventory","inventory_incomplete"),("stale","inputs_stale"),("empty","no_scored_skill_groups")])
def test_explicit_no_score_readiness(change,reason):
    values=list(components())
    if change=="unknown": values[2]=Component("O","unknown")
    if change=="support": values[3]=Component("Q","applicable",(None,))
    if change=="empty": values[0],values[1]=Component("R","not_applicable"),Component("P","not_applicable")
    result=assess(tuple(values),inventory_complete=change!="inventory",current=change!="stale")
    assert result["alignment"] is None and reason in result["reasons"]


def test_not_applicable_reweights_without_unknown_zero_credit():
    values=(Component("R","applicable",(F(1),)),Component("P","not_applicable"),
            Component("O","not_applicable"),Component("Q","not_applicable"))
    assert assess(values,inventory_complete=True,current=True)["alignment"] == 100


def test_ties_use_exact_fraction_then_rank_then_canonical_uuid():
    a="AAAAAAAA-0000-0000-0000-000000000000"
    b="bbbbbbbb-0000-0000-0000-000000000000"
    assert tie_key(F(1,3),2,a) < tie_key(F(333333,1000000),1,b)
    assert tie_key(F(1),1,b) < tie_key(F(1),2,a)
    assert tie_key(F(1),1,a) < tie_key(F(1),1,b)


@pytest.mark.parametrize("status", ["Approved","accepted","",None])
def test_noncanonical_review_is_not_coerced(status):
    with pytest.raises(ValueError): Occurrence("x","Python","skill",status)


def test_actual_concept_deduplication_retains_every_evidence_reference():
    requirements=(Occurrence("r1","Python","skill",links=(Link("r","a"),)),
                  Occurrence("r2","Python programming","tool",links=(Link("r","a"),Link("r","a"))),
                  Occurrence("r3","Docker","tool",links=(Link("r","b"),)))
    candidate=(Occurrence("c1","Python","skill",links=(Link("r","a"),)),)
    group=occupational_group("AND",requirements,candidate,frozenset({"r"}))
    assert group["support"]==F(1,2) and group["status"]=="Partially Covered"
    assert len(group["assessments"])==3


def test_incomparable_explanation_is_not_absent_evidence():
    result=occupational_group("SINGLE",(Occurrence("r","Python","skill",links=(Link("r","a"),)),),
                             (Occurrence("c","Python","skill"),),frozenset({"r"}))
    assert result["support"]==0 and result["status"]=="Missing"
    assert result["warnings"]==("identity_incomparable",)
    assert "not evidenced" not in support_explanation(result["assessments"][0]["best"]).lower()
    with pytest.raises(ValueError):
        occupational_group("SINGLE",(Occurrence("r","Degree","qualification"),),(),frozenset())

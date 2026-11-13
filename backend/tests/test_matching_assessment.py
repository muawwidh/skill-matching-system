"""Synthetic snapshot tests; no database, model, corpus or retrieval writes."""
from copy import deepcopy
from fractions import Fraction as F
from uuid import UUID

import pytest

from app.matching.assessment import assess_inputs


def skill(key, text="Python", kind="skill", **values):
    return {"id": key, "normalized_text": text, "raw_text": text,
            "skill_type": kind, "review_status": "approved", "extracted_term_id": None,
            "requirement_type": "required", **values}


def fact(key, kind="qualification", **values):
    return {"id": key, "fact_type": kind, "review_status": "approved",
            "statement": "Bachelor of Computer Science", "completion": "completed",
            "field": "computer science", "scope": "undergraduate qualification",
            "duration_months": None, "taxonomy_concept_id": None, "taxonomy_release_id": None,
            "evidence_reference": "source:" + str(key), "source_fingerprint": "source", **values}


def states():
    taxonomy = {"links": [], "concepts": [], "releases": []}
    candidate = {"skills": [skill("c")], "facts": [], "taxonomy": deepcopy(taxonomy)}
    job = {"skills": [skill("j")], "facts": [], "taxonomy": deepcopy(taxonomy),
           "fact_taxonomy": deepcopy(taxonomy), "fingerprint": "inventory", "source_fingerprint": "source",
           "inventory_current": True, "inventory": {"review_status": "approved", "inventory_complete": True,
               "source_fingerprint": "inventory", "o_applicability": "not_applicable",
               "o_reason": "no_occupation_scope_stated", "q_applicability": "not_applicable",
               "q_reason": "no_qualification_or_experience_scope_stated"},
           "groups": [{"id": "r", "component": "R", "operator": "SINGLE", "classification": "required",
                       "critical": False, "review_status": "approved", "source_fingerprint": "source"}],
           "members": [{"id": "m", "group_id": "r", "job_skill_id": "j", "job_matching_fact_id": None}],
           "occurrences": []}
    return candidate, job


def add_q(candidate, job, requirement=None, evidence=None):
    job["facts"].append(requirement or fact("qj"))
    if evidence is not None:
        candidate["facts"].append(evidence)
    job["groups"].append({**job["groups"][0], "id": "q", "component": "Q"})
    job["members"].append({"id": "qm", "group_id": "q", "job_skill_id": None,
                           "job_matching_fact_id": job["facts"][-1]["id"]})
    job["inventory"].update(q_applicability="applicable", q_reason=None)


def run(candidate, job, releases=frozenset()):
    return assess_inputs(candidate, job, releases)


def test_contract_non_null_exact_score_and_no_input_mutation_or_raw_snapshot():
    candidate, job = states()
    candidate["raw_text"] = "PRIVATE CV MUST NEVER LEAK"
    candidate["skills"][0]["evidence_sentence"] = "PRIVATE CV MUST NEVER LEAK"
    before = deepcopy((candidate, job))
    result = run(candidate, job)
    assert set(result) == {"assessment", "groups", "evidence", "warnings", "unknown_occurrences"}
    assert result["assessment"]["alignment"] == F(100)
    assert result["groups"][0]["support"] == F(1)
    assert result["groups"][0]["classification"] == "required"
    assert result["evidence"][0]["candidate_id"] == "c"
    assert result["evidence"][0]["member_id"] == "m"
    assert "PRIVATE CV" not in repr(result)
    assert (candidate, job) == before


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_only_approved_candidate_evidence_contributes(status):
    candidate, job = states()
    candidate["skills"][0]["review_status"] = status
    result = run(candidate, job)
    assert result["groups"][0]["support"] == 0
    assert result["evidence"][0]["reason_code"] == "not_evidenced"
    add_q(candidate, job, evidence=fact("qc", review_status=status))
    result = run(candidate, job)
    assert result["assessment"]["provisional"]
    assert next(g for g in result["groups"] if g["component"] == "Q")["support"] is None


@pytest.mark.parametrize("changes,expected,reason", [
    ({}, F(1), "qualification_satisfied"),
    ({"completion": "in_progress"}, F(0), "qualification_completion_contradicted"),
    ({"completion": "not_completed"}, F(0), "qualification_completion_contradicted"),
    ({"completion": "unknown"}, None, "qualification_completion_unknown"),
    ({"statement": "Master of Computer Science"}, None, "qualification_equivalence_unknown"),
    ({"field": ""}, None, "fact_field_or_scope_unknown"),
    ({"scope": "another scope"}, None, "fact_field_or_scope_unknown"),
])
def test_qualification_explicit_completion_no_degree_hierarchy(changes, expected, reason):
    candidate, job = states()
    add_q(candidate, job, evidence=fact("qc", **changes))
    result = run(candidate, job)
    group = next(g for g in result["groups"] if g["component"] == "Q")
    assert group["support"] == expected
    assert group["assessments"][0]["best"].reason == reason
    row = next(x for x in result["evidence"] if x["component"] == "Q")
    assert row["candidate_evidence_reference"] == "source:qc"
    assert row["requirement_evidence_reference"] == "source:qj"
    assert "deterministically" in row["explanation"]
    assert result["assessment"]["provisional"] == (expected is None)


@pytest.mark.parametrize("months,scope,expected", [(36, "backend", F(1)), (12, "backend", F(0)),
                                                 (None, "backend", None), (36, "frontend", None)])
def test_experience_uses_only_bounded_duration_in_same_explicit_scope(months, scope, expected):
    candidate, job = states()
    add_q(candidate, job, fact("qj", "experience", duration_months=24, scope="backend"),
          fact("qc", "experience", duration_months=months, scope=scope))
    result = run(candidate, job)
    assert next(g for g in result["groups"] if g["component"] == "Q")["support"] == expected


def test_experience_durations_are_not_added_and_unknown_alternative_propagates():
    candidate, job = states()
    add_q(candidate, job, fact("qj", "experience", duration_months=24), fact("qc", "experience", duration_months=12))
    candidate["facts"].append(fact("qc2", "experience", duration_months=12))
    assert next(g for g in run(candidate, job)["groups"] if g["component"] == "Q")["support"] == 0
    candidate["facts"].append(fact("qc3", "experience", duration_months=None))
    assert next(g for g in run(candidate, job)["groups"] if g["component"] == "Q")["support"] is None


@pytest.mark.parametrize("job_completion,candidate_completion,expected,reason", [
    ("completed", "completed", F(1), "experience_duration_satisfied"),
    ("completed", "in_progress", F(0), "experience_completion_contradicted"),
    ("completed", "not_completed", F(0), "experience_completion_contradicted"),
    ("completed", "unknown", None, "experience_completion_unknown"),
    ("completed", "not_applicable", None, "experience_completion_unknown"),
    ("not_applicable", "in_progress", F(1), "experience_duration_satisfied"),
    ("not_applicable", "unknown", F(1), "experience_duration_satisfied"),
    ("unknown", "completed", None, "experience_completion_unknown"),
    ("in_progress", "completed", None, "experience_completion_unknown"),
    ("not_completed", "completed", None, "experience_completion_unknown"),
])
def test_experience_completion_constraint_is_explicit_and_never_inferred(job_completion, candidate_completion, expected, reason):
    candidate, job = states()
    add_q(candidate, job, fact("qj", "experience", duration_months=24, completion=job_completion),
          fact("qc", "experience", duration_months=36, completion=candidate_completion))
    result = run(candidate, job)
    group = next(g for g in result["groups"] if g["component"] == "Q")
    assert group["support"] == expected
    assert group["assessments"][0]["best"].reason == reason
    assert result["assessment"]["provisional"] == (expected is None)
    if expected == 0:
        assert result["assessment"]["alignment"] == F(175, 2)


@pytest.mark.parametrize("concept,release,selected,expected", [
    ("occupation", "release", frozenset({"release"}), F(1)),
    ("other", "release", frozenset({"release"}), None),
    ("occupation", "old", frozenset({"release", "old"}), None),
    ("occupation", "release", frozenset(), None),
])
def test_occupation_never_infers_mismatch_from_title_or_different_concept(concept, release, selected, expected):
    candidate, job = states()
    job["facts"] = [fact("oj", "occupation", taxonomy_concept_id="occupation", taxonomy_release_id="release")]
    candidate["facts"] = [fact("oc", "occupation", taxonomy_concept_id=concept, taxonomy_release_id=release)]
    job["inventory"].update(o_applicability="applicable", o_reason=None)
    result = run(candidate, job, selected)
    group = next(g for g in result["groups"] if g["component"] == "O")
    assert group["group_id"] is None and group["support"] == expected
    assert group["assessments"][0]["requirement_id"] == "oj"


def test_job_skill_q_requires_explicit_fact_instead_of_parsing_phrase():
    candidate, job = states()
    job["skills"].append(skill("degree", "Completed bachelor degree", "qualification"))
    job["groups"].append({**job["groups"][0], "id": "q", "component": "Q"})
    job["members"].append({"id": "qm", "group_id": "q", "job_skill_id": "degree", "job_matching_fact_id": None})
    job["inventory"].update(q_applicability="applicable", q_reason=None)
    result = run(candidate, job)
    assert result["assessment"]["provisional"]
    assert "explicit_q_fact_required" in result["warnings"]


@pytest.mark.parametrize("operator,expected", [("OR", F(1)), ("AND", None)])
def test_mixed_q_group_assesses_approved_fact_and_unsupported_phrase_independently(operator, expected):
    candidate, job = states()
    add_q(candidate, job, evidence=fact("qc"))
    job["groups"][-1]["operator"] = operator
    job["skills"].append(skill("degree", "Alternative qualification", "qualification"))
    job["members"].append({"id": "phrase", "group_id": "q", "job_skill_id": "degree", "job_matching_fact_id": None})
    result = run(candidate, job)
    group = next(g for g in result["groups"] if g["component"] == "Q")
    assert group["support"] == expected
    assert {x["requirement_id"]: x["best"].value for x in group["assessments"]} == {"degree": None, "qj": F(1)}
    assert "explicit_q_fact_required" in group["warnings"]
    assert "inventory_incomplete" not in result["assessment"]["reasons"]
    assert result["assessment"]["provisional"] == (expected is None)
    rows = [x for x in result["evidence"] if x["component"] == "Q"]
    assert {x["member_id"] for x in rows} == {"phrase", "qm"}
    assert next(x for x in rows if x["member_id"] == "qm")["candidate_evidence_reference"] == "source:qc"
    if expected == 1:
        assert result["assessment"]["alignment"] == F(100)


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_satisfied_q_or_does_not_hide_unapproved_inventory_member(status):
    candidate, job = states()
    add_q(candidate, job, evidence=fact("qc"))
    job["groups"][-1]["operator"] = "OR"
    job["skills"].append(skill("degree", "Alternative qualification", "qualification", review_status=status))
    job["members"].append({"id": "phrase", "group_id": "q", "job_skill_id": "degree", "job_matching_fact_id": None})
    result = run(candidate, job)
    assert result["assessment"]["provisional"]
    assert "inventory_incomplete" in result["assessment"]["reasons"]


@pytest.mark.parametrize("change", ["pending", "rejected", "deleted", "stale"])
def test_unavailable_group_evidence_is_provisional_not_exception(change):
    candidate, job = states()
    if change == "deleted":
        job["skills"] = []
    elif change == "stale":
        job["groups"][0]["source_fingerprint"] = "old"
    else:
        job["skills"][0]["review_status"] = change
    result = run(candidate, job)
    assert result["assessment"]["alignment"] is None
    assert result["groups"][0]["support"] is None


@pytest.mark.parametrize("change", ["unknown", "noncanonical", "pending", "stale_signoff", "no_signoff", "stale_review"])
def test_inventory_flags_cannot_hide_unresolved_inputs(change):
    candidate, job = states()
    if change == "unknown":
        job["skills"][0]["requirement_type"] = "unknown"
    elif change == "noncanonical":
        job["skills"][0]["requirement_type"] = "Required"
    elif change == "pending":
        job["skills"][0]["review_status"] = "pending"
    elif change == "stale_signoff":
        job["inventory"]["source_fingerprint"] = "old"
    elif change == "no_signoff":
        job["inventory"] = None
    else:
        job["occurrences"] = [{"id": "review", "job_skill_id": "j", "classification": "required", "review_status": "approved", "source_fingerprint": "old", "reason": "reviewed"}]
    result = run(candidate, job)
    assert result["assessment"]["provisional"]
    assert "inventory_incomplete" in result["assessment"]["reasons"]


def link(state, key, concept, release="release"):
    state["skills"][0]["extracted_term_id"] = key
    state["taxonomy"]["links"] = [{"extracted_term_id": key, "concept_id": concept}]
    state["taxonomy"]["concepts"] = [{"id": concept, "taxonomy_version_id": release}]


def test_skill_taxonomy_conflict_and_each_evidence_reason_survives():
    candidate, job = states()
    link(candidate, "ct", "one")
    link(job, "jt", "two")
    candidate["skills"].append(skill("unlinked"))
    result = run(candidate, job, frozenset({"release"}))
    assert {x["reason_code"] for x in result["evidence"]} == {"identity_mismatch", "identity_incomparable"}
    assert "identity_incomparable" in result["warnings"]
    assert result["assessment"]["alignment"] == 0


def test_stale_taxonomy_term_fails_closed_not_text_fallback():
    candidate, job = states()
    link(candidate, "ct", "one")
    candidate["taxonomy"]["terms"] = [{"id": "ct", "raw_text": "Java", "normalized_text": "Java", "term_type": "skill"}]
    with pytest.raises(ValueError, match="identity is stale"):
        run(candidate, job)


@pytest.mark.parametrize("kind", ["qualification", "experience", "occupation", "unknown"])
def test_non_capability_candidate_skills_cannot_gain_taxonomy_credit(kind):
    candidate, job = states()
    link(candidate, "ct", "one")
    link(job, "jt", "one")
    candidate["skills"][0]["skill_type"] = kind
    assert run(candidate, job, frozenset({"release"}))["groups"][0]["support"] == 0


def test_unapproved_candidate_link_metadata_is_never_consulted():
    candidate, job = states()
    link(candidate, "ct", "missing-concept")
    candidate["taxonomy"]["concepts"] = []
    candidate["skills"][0]["review_status"] = "pending"
    assert run(candidate, job)["groups"][0]["support"] == 0


def test_group_deduplication_exact_partial_critical_penalty_and_order_independence():
    candidate, job = states()
    job["groups"][0].update(operator="AND", critical=True)
    for key, text in (("j2", " Python "), ("j3", "Docker")):
        job["skills"].append(skill(key, text, "tool"))
        job["members"].append({"id": "m" + key, "group_id": "r", "job_skill_id": key, "job_matching_fact_id": None})
    result = run(candidate, job)
    assert result["groups"][0]["support"] == F(1, 2)
    assert result["groups"][0]["status"] == "Partially Covered"
    assert len(result["groups"][0]["assessments"]) == 3
    assert result["assessment"]["alignment"] == 45
    for key in ("groups", "members", "skills"):
        job[key].reverse()
    assert run(candidate, job) == result


def test_or_positive_fact_overrides_unknown_alternative():
    candidate, job = states()
    add_q(candidate, job, evidence=fact("qc"))
    job["groups"][-1]["operator"] = "OR"
    job["facts"].append(fact("qj2", statement="Alternative credential"))
    job["members"].append({"id": "qm2", "group_id": "q", "job_skill_id": None, "job_matching_fact_id": "qj2"})
    assert run(candidate, job)["assessment"]["alignment"] == 100
    job["groups"][-1]["operator"] = "AND"
    assert run(candidate, job)["assessment"]["provisional"]


def test_uuid_snapshot_ids_and_selected_releases_are_normalized():
    candidate, job = states()
    key = UUID("00000000-0000-0000-0000-000000000001")
    job["skills"][0]["id"] = key
    job["members"][0]["job_skill_id"] = key
    assert run(candidate, job)["evidence"][0]["requirement_id"] == str(key)


def test_incomplete_snapshot_and_malformed_structure_are_distinct_errors():
    candidate, job = states()
    with pytest.raises(ValueError, match="Expanded"):
        run({"facts": []}, job)
    job["members"][0]["job_matching_fact_id"] = "also"
    with pytest.raises(ValueError, match="Exactly one"):
        run(candidate, job)

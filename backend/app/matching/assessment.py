"""Pure reviewed-input adapter for matching-policy-v1.

Inputs are repository snapshots, not ORM objects. Both states must include
``skills``, ``facts`` and full skill ``taxonomy`` (links/concepts/releases).
The caller owns authorization, consistent reads and retrieval currentness.
No prose parsing, credential hierarchy, period aggregation or equivalence is
performed. Unsupported reviewed-fact comparisons abstain rather than score 0.
"""
from fractions import Fraction

from app.matching.policy import (
    CLASSIFICATIONS, REVIEWS, Component, Link, Occurrence, Support, assess, fingerprint, group_support,
    normalize, occupational_group, support_explanation,
)


FACT_EXPLANATION = (
    "Qualification/experience matching compares explicit candidate-confirmed "
    "reviewed facts deterministically; unsupported comparisons abstain as unknown. "
    "It does not infer degree equivalence, completion, experience scope or seniority."
)


class InputConsistencyError(ValueError):
    """Known reviewed-data inconsistency, not a catch-all for engine failures."""
    def __init__(self, code: str, message: str, reference: dict | None = None):
        self.code = code
        self.reference = reference or {}
        super().__init__(message)


def _id(value) -> str | None:
    return str(value) if value is not None else None


def _ordered(rows):
    return sorted(rows, key=lambda row: str(row["id"]))


def _occurrence(row: dict, taxonomy: dict) -> Occurrence:
    concepts = {_id(x["id"]): x for x in taxonomy["concepts"]}
    links = []
    for link in taxonomy["links"]:
        if row.get("extracted_term_id") is None or _id(link["extracted_term_id"]) != _id(row["extracted_term_id"]):
            continue
        if "terms" in taxonomy:
            term = next((x for x in taxonomy["terms"] if _id(x["id"]) == _id(row["extracted_term_id"])), None)
            if not term or any(row.get(key) != term.get(other) for key, other in
                               (("raw_text", "raw_text"), ("normalized_text", "normalized_text"), ("skill_type", "term_type"))):
                raise InputConsistencyError("taxonomy_identity_stale", "Taxonomy term/skill identity is stale or incomplete",
                    {"occurrence_id": str(row["id"]), "extracted_term_id": str(row["extracted_term_id"])})
        concept = concepts.get(_id(link["concept_id"]))
        if concept is None:
            raise InputConsistencyError("taxonomy_snapshot_incomplete", "Incomplete taxonomy snapshot for skill link")
        # ApprovedTaxonomyLink has no review_status; the table itself is approved.
        links.append(Link(str(concept["taxonomy_version_id"]), str(concept["id"]),
                          link.get("review_status", "approved")))
    return Occurrence(str(row["id"]), row["normalized_text"], row["skill_type"],
                      row["review_status"], tuple(links))


def _fact_support(candidate: dict, requirement: dict, releases: frozenset[str]) -> Support:
    unknown = Support(None, "fact_comparison_unsupported", str(candidate["id"]))
    if candidate["fact_type"] != requirement["fact_type"]:
        return unknown
    if requirement["fact_type"] == "occupation":
        left = (_id(candidate.get("taxonomy_release_id")), _id(candidate.get("taxonomy_concept_id")))
        right = (_id(requirement.get("taxonomy_release_id")), _id(requirement.get("taxonomy_concept_id")))
        if all(left) and left == right and left[0] in releases:
            return Support(Fraction(1), "occupation_identity_match", str(candidate["id"]))
        # Different concepts/titles do not constitute reviewed incompatibility.
        return Support(None, "occupation_alignment_unknown", str(candidate["id"]))
    if requirement["fact_type"] not in {"qualification", "experience"}:
        return unknown
    if any(not normalize(requirement.get(key, "")) or
           normalize(requirement[key]) != normalize(candidate.get(key, ""))
           for key in ("field", "scope")):
        return Support(None, "fact_field_or_scope_unknown", str(candidate["id"]))
    if requirement["fact_type"] == "qualification":
        if requirement.get("duration_months") is not None:
            return Support(None, "fact_comparison_unsupported", str(candidate["id"]))
        if not normalize(requirement.get("statement", "")) or normalize(requirement["statement"]) != normalize(candidate.get("statement", "")):
            return Support(None, "qualification_equivalence_unknown", str(candidate["id"]))
        if requirement.get("completion") != "completed" or candidate.get("completion") not in {"completed", "in_progress", "not_completed"}:
            return Support(None, "qualification_completion_unknown", str(candidate["id"]))
        value = Fraction(int(candidate["completion"] == "completed"))
        return Support(value, "qualification_satisfied" if value else "qualification_completion_contradicted", str(candidate["id"]))
    completion = requirement.get("completion")
    if completion == "completed":
        if candidate.get("completion") in {"in_progress", "not_completed"}:
            return Support(Fraction(0), "experience_completion_contradicted", str(candidate["id"]))
        if candidate.get("completion") != "completed":
            return Support(None, "experience_completion_unknown", str(candidate["id"]))
    elif completion != "not_applicable":
        return Support(None, "experience_completion_unknown", str(candidate["id"]))
    months = candidate.get("duration_months"), requirement.get("duration_months")
    if any(type(x) is not int or x < 0 for x in months):
        return Support(None, "experience_duration_unknown", str(candidate["id"]))
    value = Fraction(int(months[0] >= months[1]))
    return Support(value, "experience_duration_satisfied" if value else "experience_duration_below_requirement", str(candidate["id"]))


def _fact_assessment(requirement, candidates, releases):
    rows = tuple(_fact_support(x, requirement, releases) for x in candidates
                 if x["review_status"] == "approved" and x["fact_type"] == requirement["fact_type"])
    # Positive explicit evidence wins; absent/unsupported facts are unknown, not zero.
    positives = [x for x in rows if x.value == 1]
    known = [x for x in rows if x.value is not None]
    unknowns = [x for x in rows if x.value is None]
    best = (positives or unknowns or known
            or [Support(None, "approved_fact_unavailable")])[0]
    return {"requirement_id": str(requirement["id"]), "best": best, "occurrences": rows}


def _fact_key(row):
    return fingerprint({key: normalize(row.get(key, "")) for key in ("fact_type", "statement", "field", "scope", "completion")} |
                       {"duration_months": row.get("duration_months"),
                        "concept": _id(row.get("taxonomy_concept_id")), "release": _id(row.get("taxonomy_release_id"))})


def _status(value):
    return "unassessed" if value is None else "Matched" if value == 1 else "Missing" if value == 0 else "Partially Covered"


def assess_inputs(candidate_state: dict, job_state: dict, selected_releases: frozenset[str]) -> dict:
    """Return assessment/groups/evidence/warnings/unknown_occurrences, exactly.

    Group assessments use policy.Support objects. Evidence rows retain only
    source IDs/references and deterministic reasons, never whole input snapshots.
    Occupation requirements have group_id/member_id=None and their fact IDs.
    A stale inventory permits diagnostic assessments, never a complete score.
    """
    for state in (candidate_state, job_state):
        if not {"skills", "facts", "taxonomy"} <= state.keys():
            raise ValueError("Expanded skills/facts/taxonomy snapshots are required")
        if not {"links", "concepts", "releases"} <= state["taxonomy"].keys():
            raise ValueError("Full taxonomy snapshot required")
    releases = frozenset(str(x) for x in selected_releases)
    candidates = tuple(_occurrence(x, candidate_state["taxonomy"]) for x in _ordered(candidate_state["skills"])
                       if x["review_status"] == "approved" and
                       x["skill_type"] in {"skill", "tool", "domain_knowledge", "language"})
    facts = _ordered(candidate_state["facts"])
    skills = {_id(x["id"]): x for x in job_state["skills"]}
    job_facts = {_id(x["id"]): x for x in job_state["facts"]}
    inventory = job_state.get("inventory") or {}
    current = bool(job_state.get("inventory_current") and inventory.get("source_fingerprint") == job_state.get("fingerprint"))
    complete = bool(current and inventory.get("review_status") == "approved" and inventory.get("inventory_complete"))
    groups, evidence, unknown_occurrences = [], [], []
    used_skills, used_facts = set(), set()
    source = job_state.get("source_fingerprint")

    def record(group, members, requirements, result):
        group_row = {"group_id": _id(group.get("id")), "component": group["component"],
                     "operator": group["operator"], "classification": group.get("classification"),
                     "critical": group.get("critical", False), **result}
        groups.append(group_row)
        for member, requirement, item in zip(members, requirements, result["assessments"]):
            for support in item["occurrences"] or (item["best"],):
                candidate = next((x for x in facts if str(x["id"]) == support.occurrence_id), {}) if group["component"] in {"O", "Q"} else {}
                evidence.append({"group_id": group_row["group_id"], "component": group["component"],
                                 "member_id": _id(member.get("id")), "requirement_id": str(requirement["id"]),
                                 "candidate_id": support.occurrence_id, "support": support.value,
                                 "reason_code": support.reason,
                                 "candidate_evidence_reference": candidate.get("evidence_reference"),
                                 "candidate_extracted_term_id": next((_id(x.get("extracted_term_id")) for x in candidate_state["skills"] if str(x["id"]) == support.occurrence_id), None),
                                 "requirement_extracted_term_id": _id(requirement.get("extracted_term_id")),
                                 "requirement_evidence_reference": requirement.get("evidence_reference"),
                                 "explanation": FACT_EXPLANATION if group["component"] in {"O", "Q"} else
                                 "Unresolved inventory evidence cannot be assessed." if support.reason == "unresolved_inventory_occurrence" else support_explanation(support)})

    for group in _ordered(job_state["groups"]):
        if group["critical"] and (group["component"] != "R" or group["classification"] != "required"
                                  or group["review_status"] != "approved"):
            raise InputConsistencyError("invalid_critical_group", "Critical support requires an approved required-skill group R",
                {"group_id": str(group["id"]), "component": group["component"], "classification": group["classification"]})
        if group["review_status"] != "approved":
            complete = False
            continue
        if group["source_fingerprint"] != source:
            complete = False
        component = group["component"]
        if component not in {"R", "P", "Q"} or group["classification"] not in {"required", "preferred"} or (component in {"R", "P"} and group["classification"] != {"R": "required", "P": "preferred"}[component]):
            raise InputConsistencyError("invalid_group_classification", "Invalid group component/classification")
        members = _ordered([x for x in job_state["members"] if _id(x["group_id"]) == _id(group["id"])])
        if not members or group["operator"] not in {"SINGLE", "OR", "AND"} or (group["operator"] == "SINGLE" and len(members) != 1):
            raise InputConsistencyError("invalid_group_structure", "Invalid one-level group structure")
        requirements = []
        for member in members:
            skill_id, fact_id = _id(member.get("job_skill_id")), _id(member.get("job_matching_fact_id"))
            if (skill_id is None) == (fact_id is None):
                raise InputConsistencyError("invalid_member_reference", "Exactly one member source required")
            key = skill_id or fact_id
            used = used_skills if skill_id else used_facts
            if key in used:
                raise InputConsistencyError("duplicate_group_membership", "Source belongs to more than one group")
            used.add(key)
            row = (skills if skill_id else job_facts).get(key)
            if row is None:
                row = {"id": key, "review_status": "pending", "fact_type": "unavailable", "skill_type": "unavailable"}
            if component == "Q" and row.get("fact_type", row.get("skill_type")) not in {"qualification", "experience", "unavailable"}:
                raise InputConsistencyError("invalid_q_member", "Q requires qualification/experience evidence")
            if component != "Q" and not skill_id:
                raise InputConsistencyError("invalid_capability_member", "R/P requires occupational skills")
            if component != "Q" and row["review_status"] == "approved" and row.get("skill_type") not in {
                    "skill", "tool", "domain_knowledge", "language"}:
                raise InputConsistencyError("invalid_capability_member", "R/P requires occupational capabilities")
            requirements.append(row)
        unavailable = (group["source_fingerprint"] != source or any(
            x["review_status"] != "approved" or
            (component != "Q" and x.get("requirement_type") not in CLASSIFICATIONS) or
            (component == "Q" and x.get("source_fingerprint", source) != source)
            for x in requirements))
        if unavailable:
            complete = False
            reason = "unresolved_inventory_occurrence"
            result = {"support": None, "status": "unassessed", "assessments": tuple(
                {"requirement_id": str(x["id"]), "best": Support(None, reason), "occurrences": ()} for x in requirements),
                "warnings": (reason,)}
        elif component == "Q":
            # An approved phrase is reviewed inventory, but not a structured fact.
            # Keep that member unknown and let the existing group rules propagate it.
            items = tuple(
                {"requirement_id": str(row["id"]), "best": Support(None, "explicit_q_fact_required"), "occurrences": ()}
                if member.get("job_skill_id") is not None else _fact_assessment(row, facts, releases)
                for member, row in zip(members, requirements))
            keys = tuple(
                fingerprint(("q_phrase", row["skill_type"], normalize(row["normalized_text"])))
                if member.get("job_skill_id") is not None else _fact_key(row)
                for member, row in zip(members, requirements))
            value = group_support(group["operator"], tuple((key, item["best"].value) for key, item in zip(keys, items)))
            result = {"support": value, "status": _status(value), "assessments": items,
                      "warnings": tuple(sorted({x["best"].reason for x in items if x["best"].value is None}))}
        else:
            result = occupational_group(group["operator"], tuple(_occurrence(x, job_state["taxonomy"]) for x in requirements), candidates, releases)
        record(group, members, requirements, result)

    for requirement in _ordered(job_state["facts"]):
        if requirement["review_status"] == "pending":
            complete = False
        if requirement["review_status"] != "approved":
            continue
        if requirement["source_fingerprint"] != source:
            complete = False
        if requirement["fact_type"] == "occupation":
            item = _fact_assessment(requirement, facts, releases)
            value = item["best"].value
            record({"component": "O", "operator": "SINGLE"}, [{}], [requirement],
                   {"support": value, "status": _status(value), "assessments": (item,),
                    "warnings": (item["best"].reason,) if value is None else ()})
        elif str(requirement["id"]) not in used_facts:
            complete = False

    reviews = {_id(x["job_skill_id"]): x for x in job_state["occurrences"]}
    for key, skill in sorted(skills.items()):
        if skill["review_status"] == "rejected":
            continue
        review = reviews.get(key)
        classification = review["classification"] if review else skill["requirement_type"]
        valid_review = bool(review and review["review_status"] == "approved" and review["source_fingerprint"] == source and review.get("reason"))
        bound = next((x for x in job_state["groups"] if any(_id(m.get("job_skill_id")) == key and _id(m["group_id"]) == _id(x["id"]) for m in job_state["members"])), None)
        if (skill["review_status"] not in REVIEWS or skill["requirement_type"] not in CLASSIFICATIONS or
            skill["review_status"] != "approved" or (review and not valid_review) or
            classification not in CLASSIFICATIONS or classification == "unknown" or
            (classification == "non_requirement" and (not valid_review or bound)) or
            (classification in {"required", "preferred"} and (not bound or bound["classification"] != classification))):
            complete = False
            unknown_occurrences.append({"component": None, "requirement_id": key, "candidate_id": None,
                             "support": None, "reason_code": "unresolved_inventory_occurrence",
                             "classification": classification})

    components = []
    for name in "RPOQ":
        values = tuple(x["support"] for x in groups if x["component"] == name)
        if name in "RP":
            applicability = "applicable" if values else "not_applicable" if complete else "unknown"
        else:
            applicability = inventory.get(name.lower() + "_applicability", "unknown") if current and inventory.get("review_status") == "approved" else "unknown"
            reason = {"O": "no_occupation_scope_stated", "Q": "no_qualification_or_experience_scope_stated"}[name]
            if applicability == "not_applicable" and (values or inventory.get(name.lower() + "_reason") != reason):
                applicability = "unknown"
        components.append(Component(name, applicability, values if applicability != "not_applicable" else ()))
    critical = tuple(x["support"] for x in groups if x["critical"])
    if any(x["critical"] and x["component"] != "R" for x in groups):
        raise InputConsistencyError("invalid_critical_group", "Critical support requires required-skill group R")
    return {"assessment": assess(tuple(components), inventory_complete=complete, current=current, critical=critical),
            "groups": tuple(groups), "evidence": tuple(evidence),
            "warnings": tuple(sorted({w for group in groups for w in group["warnings"]} |
                                     ({"unresolved_inventory_occurrence"} if unknown_occurrences else set()))),
            "unknown_occurrences": tuple(unknown_occurrences)}

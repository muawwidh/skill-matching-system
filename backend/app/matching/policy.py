"""Pure, exact matching-policy-v1 rules. No database or inference dependencies."""
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from typing import Literal


POLICY_VERSION = "matching-policy-v1"
CANONICAL_CONFIGURATION = json.dumps({
    "policy_version": POLICY_VERSION,
    "component_weights": {"required": 7, "preferred": 3, "occupation": 2, "qualification_experience": 1},
    "dense_numeric_weight": 0, "relationship_allowlist": [], "critical_penalty_cap": "0.10",
    "evidence_review_status": "approved", "unknown_requirement_policy": "visible_unscored",
    "readiness": "resolved_applicability_complete_inventory_full_assessment",
    "group_operators": ["SINGLE", "OR", "AND"], "nested_groups": False,
    "arithmetic": "exact_rational", "critical_aggregation": "maximum_missing_support",
    "retrieval": {"template": "e5-job-profile-v2", "primary_pool": 20},
    "tie_break": ["exact_alignment_desc", "original_retrieval_rank_asc", "lowercase_canonical_job_uuid_asc"],
}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
POLICY_HASH = hashlib.sha256(CANONICAL_CONFIGURATION.encode()).hexdigest()
WEIGHTS = (7, 3, 2, 1)
REVIEWS = frozenset({"approved", "pending", "rejected"})
CLASSIFICATIONS = frozenset({"required", "preferred", "non_requirement", "unknown"})


def validate_configuration(value: str) -> None:
    """V1 is immutable, including an exactly empty relationship allowlist."""
    parsed = json.loads(value)
    if json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False) != CANONICAL_CONFIGURATION:
        raise ValueError("Configuration differs from immutable matching-policy-v1")


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, default=str).encode()).hexdigest()


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def compatibility_family(kind: str) -> str | None:
    return {"skill": "technical_capability", "tool": "technical_capability",
            "domain_knowledge": "domain_knowledge", "language": "language"}.get(kind)


@dataclass(frozen=True)
class Link:
    release: str
    concept: str
    review_status: str = "approved"


@dataclass(frozen=True)
class Occurrence:
    id: str
    text: str
    kind: str
    review_status: str = "approved"
    links: tuple[Link, ...] = ()

    def __post_init__(self):
        if self.review_status not in REVIEWS or any(x.review_status not in REVIEWS for x in self.links):
            raise ValueError("Noncanonical review status")


@dataclass(frozen=True)
class Support:
    value: Fraction | None
    reason: str
    occurrence_id: str | None = None


def identity(candidate: Occurrence, requirement: Occurrence, releases: frozenset[str]) -> Support:
    if candidate.review_status != "approved" or requirement.review_status != "approved":
        return Support(Fraction(0), "unapproved_evidence", candidate.id)
    left = {(x.release, x.concept) for x in candidate.links
            if x.review_status == "approved" and x.release in releases}
    right = {(x.release, x.concept) for x in requirement.links
             if x.review_status == "approved" and x.release in releases}
    if left or right:
        shared = {x[0] for x in left} & {x[0] for x in right}
        if not shared:
            return Support(Fraction(0), "identity_incomparable", candidate.id)
        return Support(Fraction(bool(left & right)),
                       "identity_match" if left & right else "identity_mismatch", candidate.id)
    # Approved historical identities cannot be erased by text fallback. Rejected/pending links are not identity evidence.
    approved_left = {x.release for x in candidate.links if x.review_status == "approved"}
    approved_right = {x.release for x in requirement.links if x.review_status == "approved"}
    if approved_left or approved_right:
        return Support(Fraction(0), "identity_incomparable", candidate.id)
    compatible = compatibility_family(candidate.kind) is not None and compatibility_family(candidate.kind) == compatibility_family(requirement.kind)
    matched = compatible and bool(normalize(candidate.text)) and normalize(candidate.text) == normalize(requirement.text)
    return Support(Fraction(int(matched)), "text_only_match" if matched else "not_evidenced", candidate.id)


def requirement_support(candidates: tuple[Occurrence, ...], requirement: Occurrence,
                        releases: frozenset[str]) -> tuple[Support, tuple[Support, ...]]:
    assessments = tuple(identity(x, requirement, releases) for x in sorted(candidates, key=lambda x: x.id)
                        if x.review_status == "approved")
    if not assessments:
        return Support(Fraction(0), "not_evidenced"), ()
    best = min(assessments, key=lambda x: (-x.value, x.reason, x.occurrence_id))
    return best, assessments


def group_support(operator: Literal["SINGLE", "OR", "AND"], members) -> Fraction | None:
    distinct: dict[str, Fraction | None] = {}
    for index, member in enumerate(members):
        identity_key, value = member if isinstance(member, tuple) else (str(index), member)
        if type(value) is int:
            value = Fraction(value)
        if value is not None and (not isinstance(value, Fraction) or not 0 <= value <= 1):
            raise ValueError("Support must be an exact Fraction in [0,1] or unknown")
        if identity_key in distinct and distinct[identity_key] != value:
            raise ValueError("Conflicting duplicate member")
        distinct[identity_key] = value
    values = tuple(distinct.values())
    if not values or operator not in {"SINGLE", "OR", "AND"} or (operator == "SINGLE" and len(values) != 1):
        raise ValueError("Invalid one-level group")
    if operator == "OR" and Fraction(1) in values:
        return Fraction(1)
    if None in values:
        return None
    if operator == "OR":
        return max(values)
    return sum(values, Fraction(0)) / len(values)


def occupational_group(operator: Literal["SINGLE", "OR", "AND"], requirements: tuple[Occurrence, ...],
                       candidates: tuple[Occurrence, ...], releases: frozenset[str]) -> dict:
    """Deduplicate concept/evidence identities before group arithmetic, retaining all comparisons."""
    members = []
    assessments = []
    for requirement in requirements:
        if requirement.review_status != "approved" or requirement.kind not in {"skill", "tool", "domain_knowledge", "language"}:
            raise ValueError("R/P groups require approved occupational capability requirements; qualification/experience use Q")
        concepts = sorted({(link.release, link.concept) for link in requirement.links
                           if link.review_status == "approved" and link.release in releases})
        historical = sorted({(link.release, link.concept) for link in requirement.links if link.review_status == "approved"})
        key = fingerprint(("concept", concepts or historical)) if concepts or historical else fingerprint(
            ("text", compatibility_family(requirement.kind), normalize(requirement.text)))
        best, rows = requirement_support(candidates, requirement, releases)
        members.append((key, best.value))
        assessments.append({"requirement_id": requirement.id, "best": best, "occurrences": rows})
    value = group_support(operator, tuple(members))
    warnings = sorted({row.reason for item in assessments for row in item["occurrences"]
                       if row.reason == "identity_incomparable"})
    return {"support": value, "status": "unassessed" if value is None else
            "Matched" if value == 1 else "Missing" if value == 0 else "Partially Covered",
            "assessments": tuple(assessments), "warnings": tuple(warnings)}


def support_explanation(value: Support) -> str:
    messages = {"identity_match": "Candidate-confirmed evidence shares the reviewed same-release concept.",
                "identity_mismatch": "The reviewed same-release concepts differ.",
                "identity_incomparable": "The candidate occurrence and requirement have incomparable taxonomy identities.",
                "text_only_match": "Candidate-confirmed evidence supports a conservative text-only match.",
                "not_evidenced": "Not evidenced in approved profile inputs.",
                "unapproved_evidence": "Pending or rejected evidence does not contribute."}
    return messages[value.reason]


@dataclass(frozen=True)
class Component:
    name: Literal["R", "P", "O", "Q"]
    applicability: Literal["applicable", "not_applicable", "unknown"]
    groups: tuple[Fraction | None, ...] = ()

    def __post_init__(self):
        if self.name not in {"R", "P", "O", "Q"} or self.applicability not in {"applicable", "not_applicable", "unknown"}:
            raise ValueError("Invalid component")
        if any(x is not None and (not isinstance(x, Fraction) or not 0 <= x <= 1) for x in self.groups):
            raise ValueError("Invalid group support")
        if self.applicability == "not_applicable" and self.groups:
            raise ValueError("Inapplicable component cannot contain groups")


def decimal_value(value: Fraction, places: int = 6) -> Decimal:
    # Use integer half-up rounding to avoid intermediate decimal double rounding.
    scaled = value * 10 ** places
    sign = -1 if scaled < 0 else 1
    scaled = abs(scaled)
    rounded = scaled.numerator // scaled.denominator
    if 2 * (scaled.numerator % scaled.denominator) >= scaled.denominator:
        rounded += 1
    with localcontext() as context:
        context.prec = max(32, len(str(rounded)) + places + 2)
        return Decimal(sign * rounded).scaleb(-places).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def fraction_string(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def validate_fraction_pair(exact: str | None, numeric: Decimal | None) -> bool:
    if exact is None or numeric is None:
        return exact is None and numeric is None
    try:
        value = Fraction(exact)
        return exact == fraction_string(value) and decimal_value(value) == numeric
    except (ValueError, ZeroDivisionError):
        return False


def assess(components: tuple[Component, ...], *, inventory_complete: bool,
           current: bool, critical: tuple[Fraction | None, ...] = ()) -> dict:
    if {x.name for x in components} != {"R", "P", "O", "Q"} or len(components) != 4:
        raise ValueError("Exactly four components required")
    if any(x is not None and (not isinstance(x, Fraction) or not 0 <= x <= 1) for x in critical):
        raise ValueError("Invalid critical support")
    required = next(x for x in components if x.name == "R")
    if critical and (required.applicability != "applicable" or not required.groups):
        raise ValueError("Critical inputs require applicable nonempty required-skill component R")
    ordered = sorted(components, key=lambda x: "RPOQ".index(x.name))
    reasons = []
    if not inventory_complete:
        reasons.append("inventory_incomplete")
    if not current:
        reasons.append("inputs_stale")
    if any(x.applicability == "unknown" for x in ordered):
        reasons.append("applicability_unknown")
    if not any(x.name in {"R", "P"} and x.applicability == "applicable" and x.groups for x in ordered):
        reasons.append("no_scored_skill_groups")
    if any(x.applicability == "applicable" and (not x.groups or None in x.groups) for x in ordered):
        reasons.append("assessment_incomplete")
    if None in critical:
        reasons.append("critical_support_unknown")
    weights = dict(zip("RPOQ", WEIGHTS))
    total = sum(weights[x.name] for x in ordered if x.applicability == "applicable")
    resolved = not any(x.applicability == "unknown" for x in ordered)
    details = []
    score = Fraction(0)
    for item in ordered:
        coverage = Fraction(sum(x is not None for x in item.groups), len(item.groups)) if item.groups else None
        value = (sum(item.groups, Fraction(0)) / len(item.groups)
                 if item.applicability == "applicable" and item.groups and None not in item.groups else None)
        weight = (Fraction(weights[item.name], total) if item.applicability == "applicable" and total else Fraction(0)) if resolved else None
        contribution = value * weight if value is not None and weight is not None else None
        if contribution is not None:
            score += contribution
        details.append({"component": item.name, "applicability": item.applicability,
                        "coverage": coverage, "value": value, "base_weight": weights[item.name],
                        "effective_weight": weight, "contribution": contribution})
    penalty = None if None in critical else max((1 - x for x in critical), default=Fraction(0))
    alignment = None if reasons else 100 * max(Fraction(0), min(Fraction(1), score - Fraction(1, 10) * penalty))
    return {"alignment": alignment, "exact_fraction": fraction_string(alignment) if alignment is not None else None,
            "numeric": decimal_value(alignment) if alignment is not None else None,
            "display": str(decimal_value(alignment, 2)) if alignment is not None else None,
            "provisional": bool(reasons), "reasons": tuple(reasons), "components": details,
            "critical_missing_support": penalty}


def tie_key(score: Fraction, retrieval_rank: int, job_uuid: str) -> tuple:
    from uuid import UUID
    if not isinstance(score, Fraction) or retrieval_rank < 1:
        raise ValueError("Exact score and positive retrieval rank required")
    return -score, retrieval_rank, str(UUID(job_uuid)).lower()

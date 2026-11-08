"""Explicit, file-bound query eligibility; never infer exclusions from retrieval output."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator


Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class InputHashes(PolicyModel):
    candidates: Sha256
    jobs: Sha256
    judgments: Sha256


class UndefinedMetrics(PolicyModel):
    recall_at_k: Literal["undefined"]
    mrr: Literal["undefined"]


class QueryException(PolicyModel):
    candidate_id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{1,63}$")]
    reason: Nonempty
    grade2_coverage_status: Literal["no_grade2_jobs"]
    metric_treatment: UndefinedMetrics
    exclude_from_aggregate_binary_query_denominator: StrictBool
    retain_for_graded_descriptive_analyses: StrictBool

    @field_validator("reason")
    @classmethod
    def reason_is_not_placeholder(cls, value: str) -> str:
        if value.upper() in {"TBD", "TODO", "UNKNOWN"}:
            raise ValueError("Exception reason must not be a placeholder")
        return value

    @field_validator("exclude_from_aggregate_binary_query_denominator", "retain_for_graded_descriptive_analyses")
    @classmethod
    def treatment_must_be_explicit(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Exception treatment must be explicitly true")
        return value


class EvaluationPolicy(PolicyModel):
    schema_version: Literal["phase5-evaluation-policy-v1"]
    methodology_version: Nonempty
    decision_date: str
    corpus_freeze_id: Nonempty
    corpus_sha256: Sha256
    input_sha256: InputHashes
    post_judgment_protocol_deviation: StrictBool
    exceptions: list[QueryException] = Field(min_length=1)

    @field_validator("post_judgment_protocol_deviation")
    @classmethod
    def must_declare_post_judgment_deviation(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("post_judgment_protocol_deviation must be true")
        return value

    @field_validator("decision_date")
    @classmethod
    def iso_date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Policy decision_date must use YYYY-MM-DD")
        return value

    @field_validator("methodology_version", "corpus_freeze_id")
    @classmethod
    def no_placeholder(cls, value: str) -> str:
        if value.upper() in {"TBD", "TODO", "UNKNOWN"}:
            raise ValueError("Policy methodology/freeze identity must not be a placeholder")
        return value


def _unique_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate evaluation-policy key: {key}")
        result[key] = value
    return result


def load_policy(path: Path, inputs: dict[str, Path], records: list[dict]) -> EvaluationPolicy:
    policy = EvaluationPolicy.model_validate(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys))
    for name, expected in policy.input_sha256.model_dump().items():
        if hashlib.sha256(inputs[name].read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evaluation policy {name} checksum mismatch")
    for row in records:
        if (row.get("corpus_freeze_id"), row.get("corpus_sha256")) != (policy.corpus_freeze_id, policy.corpus_sha256):
            raise ValueError("Evaluation policy freeze identity/hash mismatch in corpus or judgment records")
    return policy


def query_coverage(candidates: dict, judgments: dict, policy: EvaluationPolicy | None = None) -> dict:
    counts = {candidate: sum(row["relevance_grade"] == "2" for (c, _), row in judgments.items() if c == candidate)
              for candidate in sorted(candidates)}
    exceptions = {}
    if policy is not None:
        for item in policy.exceptions:
            if item.candidate_id in exceptions:
                raise ValueError("Evaluation policy contains duplicate candidate exceptions")
            if item.candidate_id not in candidates:
                raise ValueError("Evaluation policy has an unknown candidate")
            if counts[item.candidate_id] != 0:
                raise ValueError("Evaluation policy cannot exclude a candidate with grade-2 judgments")
            exceptions[item.candidate_id] = item
    for candidate, count in counts.items():
        if count == 0 and candidate not in exceptions:
            raise ValueError(f"Candidate {candidate} has no grade-2 relevant job (no explicit valid exception)")
    eligible = [candidate for candidate, count in counts.items() if count]
    if not eligible:
        raise ValueError("Evaluation policy leaves no evaluable grade-2 queries")
    return {"total_queries": len(candidates), "evaluable_grade2_queries": len(eligible),
            "excluded_undefined_queries": len(exceptions),
            "grade2_query_coverage": f"{len(eligible)}/{len(candidates)}",
            "aggregate_binary_query_denominator": len(eligible),
            "eligible_candidate_ids": eligible,
            "excluded_queries": [exceptions[key].model_dump() for key in sorted(exceptions)],
            "grade2_jobs_per_candidate": counts,
            "policy": None if policy is None else {
                "schema_version": policy.schema_version, "methodology_version": policy.methodology_version,
                "decision_date": policy.decision_date, "corpus_freeze_id": policy.corpus_freeze_id,
                "corpus_sha256": policy.corpus_sha256,
                "post_judgment_protocol_deviation": policy.post_judgment_protocol_deviation},
            "limitation": ("This coverage exception was adopted after the relevance judgments were collected. "
                           "Binary retrieval aggregates cover only positive-covered queries, not every frozen candidate. "
                           "Report excluded aliases/reasons and coverage prominently; undefined is not zero."
                           if exceptions else "All frozen candidates have grade-2 relevant jobs.")}


def reviewer_limitations(judgments: dict) -> dict:
    reviewers = sorted({row["reviewer_id"] for row in judgments.values()})
    return {"reviewer_ids": reviewers, "reviewer_count": len(reviewers), "single_rater": len(reviewers) == 1,
            "inter_rater_reliability_estimate": None,
            "limitation": ("Single-rater judgments are subjective; no inter-rater reliability estimate is available."
                           if len(reviewers) == 1 else
                           "Multiple reviewer IDs alone do not establish independent double labelling; no inter-rater reliability estimate is supplied.")}

"""Reviewed inputs only; no scoring, ranking or run-creation API contract."""
from typing import Literal
from fractions import Fraction
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Review = Literal["approved", "pending", "rejected"]
Classification = Literal["required", "preferred", "non_requirement", "unknown"]
Applicability = Literal["applicable", "not_applicable", "unknown"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class FactInput(Input):
    fact_type: Literal["occupation", "qualification", "experience"]
    statement: str = Field(min_length=1, max_length=1000)
    completion: Literal["unknown", "completed", "in_progress", "not_completed", "not_applicable"]
    duration_months: int | None = Field(default=None, ge=0)
    field: str = Field(default="", max_length=255)
    scope: str = Field(default="", max_length=500)
    evidence_reference: str = Field(min_length=1, max_length=255)
    review_status: Review
    cv_document_id: UUID | None = None
    taxonomy_concept_id: UUID | None = None
    taxonomy_release_id: UUID | None = None

    @model_validator(mode="after")
    def taxonomy_pair(self):
        if (self.taxonomy_concept_id is None) != (self.taxonomy_release_id is None):
            raise ValueError("Concept and release must be supplied together")
        if self.taxonomy_concept_id and self.fact_type != "occupation":
            raise ValueError("Only occupation facts use reviewed concept identity")
        return self


class MemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_skill_id: UUID | None = None
    job_matching_fact_id: UUID | None = None

    @model_validator(mode="after")
    def exclusive(self):
        if (self.job_skill_id is None) == (self.job_matching_fact_id is None):
            raise ValueError("Exactly one atomic source reference required")
        return self


class GroupInput(Input):
    component: Literal["R", "P", "Q"]
    operator: Literal["SINGLE", "OR", "AND"]
    classification: Classification
    critical: bool = Field(strict=True)
    review_status: Review
    members: list[MemberInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def consistent(self):
        ids = [(x.job_skill_id, x.job_matching_fact_id) for x in self.members]
        if len(set(ids)) != len(ids) or (self.operator == "SINGLE" and len(ids) != 1):
            raise ValueError("Distinct atomic members and valid SINGLE cardinality required")
        if self.critical and (self.component != "R" or self.review_status != "approved" or self.classification != "required"):
            raise ValueError("Only explicitly approved required-skill R groups can be critical")
        if ((self.component == "R" and self.classification != "required") or
            (self.component == "P" and self.classification != "preferred") or
            (self.component == "Q" and self.classification not in {"required", "preferred"})):
            raise ValueError("Component/classification mismatch")
        return self


class OccurrenceInput(Input):
    classification: Classification
    review_status: Review
    reason: str = Field(min_length=1, max_length=1000)


class InventoryInput(Input):
    review_status: Review
    inventory_complete: bool = Field(strict=True)
    o_applicability: Applicability
    o_reason: Literal["no_occupation_scope_stated"] | None = None
    q_applicability: Applicability
    q_reason: Literal["no_qualification_or_experience_scope_stated"] | None = None

    @model_validator(mode="after")
    def reasons(self):
        for component in ("o", "q"):
            if (getattr(self, component + "_applicability") == "not_applicable") != (getattr(self, component + "_reason") is not None):
                raise ValueError("not_applicable requires its fixed reason; other states cannot carry it")
        if self.inventory_complete and (self.review_status != "approved" or "unknown" in {self.o_applicability, self.q_applicability}):
            raise ValueError("Complete inventory requires approved review and resolved applicability")
        return self


class ComponentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["R", "P", "O", "Q"]
    applicability: Applicability
    groups: list[Fraction | None]


class PolicyAssessmentInput(BaseModel):
    """Internal contract only, not an API that computes/persists scores."""
    model_config = ConfigDict(extra="forbid")
    components: list[ComponentInput]
    critical: list[Fraction | None] = Field(default_factory=list)

    @model_validator(mode="after")
    def critical_context(self):
        if len(self.components) != 4 or {x.name for x in self.components} != {"R", "P", "O", "Q"}:
            raise ValueError("Exactly four components required")
        required = next(x for x in self.components if x.name == "R")
        if self.critical and (required.applicability != "applicable" or not required.groups):
            raise ValueError("Critical inputs require applicable nonempty required-skill component R")
        return self

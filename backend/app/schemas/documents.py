from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CandidateProfileRead(BaseModel):
    id: UUID
    user_id: UUID
    headline: str
    summary: str
    consent_to_process_cv: bool
    status: str

    model_config = {"from_attributes": True}


class CandidateProfileUpdate(BaseModel):
    headline: str = Field(default="", max_length=255)
    summary: str = ""
    consent_to_process_cv: bool = False


class SectionRead(BaseModel):
    id: UUID
    section_type: str
    heading: str
    content: str
    start_char: int
    end_char: int
    confidence_score: float
    extraction_method: str

    model_config = {"from_attributes": True}


class CvPasteRequest(BaseModel):
    text: str = Field(min_length=1)
    original_filename: str = "pasted-cv.txt"
    consent_to_process: bool


class CvDocumentRead(BaseModel):
    id: UUID
    original_filename: str
    content_type: str
    source: str
    status: str
    raw_text: str
    cleaned_text: str
    size_bytes: int
    error_message: str
    processed_at: datetime | None
    sections: list[SectionRead] = []

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(default="", max_length=255)
    location: str = Field(default="", max_length=255)
    employment_type: str = Field(default="", max_length=80)
    description: str = Field(min_length=1)


class JobUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(default="", max_length=255)
    location: str = Field(default="", max_length=255)
    employment_type: str = Field(default="", max_length=80)
    description: str = Field(min_length=1)
    status: str = "draft"


class JobRead(BaseModel):
    id: UUID
    title: str
    company: str
    location: str
    employment_type: str
    description: str
    cleaned_description: str
    status: str
    source: str
    error_message: str
    processed_at: datetime | None
    sections: list[SectionRead] = []

    model_config = {"from_attributes": True}


class ProcessingLogRead(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    stage: str
    status: str
    message: str
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateSkillRead(BaseModel):
    id: UUID
    raw_text: str
    normalized_text: str
    skill_type: str
    evidence_sentence: str
    confidence_score: float
    review_status: str
    source: str

    model_config = {"from_attributes": True}


class CandidateSkillTaxonomy(BaseModel):
    concept_id: UUID
    release_id: UUID
    external_id: str
    preferred_label: str
    source: str
    version: str


class CandidateSkillGroup(BaseModel):
    key: str
    label: str
    taxonomy: CandidateSkillTaxonomy | None = None
    occurrences: list[CandidateSkillRead]


class CandidateSkillUpsert(BaseModel):
    id: UUID | None = None
    raw_text: str = Field(min_length=1, max_length=255)
    normalized_text: str = Field(min_length=1, max_length=255)
    skill_type: str = Field(default="skill", max_length=80)
    evidence_sentence: str = ""
    review_status: str = Field(default="approved", max_length=50)


class CandidateSkillReviewRequest(BaseModel):
    skills: list[CandidateSkillUpsert]


class JobSkillRead(BaseModel):
    id: UUID
    raw_text: str
    normalized_text: str
    skill_type: str
    requirement_type: str
    evidence_sentence: str
    confidence_score: float
    review_status: str
    source: str
    source_section: str = ""

    model_config = {"from_attributes": True}


class JobSkillUpdate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=255)
    normalized_text: str = Field(min_length=1, max_length=255)
    skill_type: str = Field(default="skill", max_length=80)
    requirement_type: str = Field(default="unknown", max_length=50)
    evidence_sentence: str = ""
    review_status: str = Field(default="approved", max_length=50)


class MatchedSkillRead(BaseModel):
    label: str
    matched_via: Literal["taxonomy_concept", "skill_name"]


class MissingSkillRead(BaseModel):
    label: str
    # Name-only checks cannot rule out the skill appearing under other wording.
    checked_via: Literal["taxonomy_concept", "skill_name"]

    @model_validator(mode="before")
    @classmethod
    def _legacy_label(cls, value):
        # Rows written before D040 stored bare labels; those were all concept-checked.
        if isinstance(value, str):
            return {"label": value, "checked_via": "taxonomy_concept"}
        return value


class CandidateJobMatchRead(BaseModel):
    id: UUID
    candidate_profile_id: UUID
    job_id: UUID
    score: float
    matched_required: list[MatchedSkillRead]
    matched_preferred: list[MatchedSkillRead]
    missing_required: list[MissingSkillRead]
    missing_preferred: list[MissingSkillRead]
    candidate_skill_count: int
    job_skill_count: int
    explanation: str
    job: JobRead

    model_config = {"from_attributes": True}


# --- Administrator system overview (read-only counts; ratios are shown as "X of Y") ---

class TaxonomyReleaseCounts(BaseModel):
    source: str
    version: str
    status: str
    is_sample: bool
    skills: int
    occupations: int
    other: int
    by_type: dict[str, int]


class MappingReleaseCounts(BaseModel):
    esco_version: str
    onet_version: str
    rows: int


class TaxonomyOverview(BaseModel):
    releases: list[TaxonomyReleaseCounts]
    esco_onet_mappings_total: int
    esco_onet_mappings: list[MappingReleaseCounts]


class CvCounts(BaseModel):
    uploaded: int
    processed: int
    failed: int
    failed_note: str


class CandidateOverview(BaseModel):
    accounts: int
    cvs: CvCounts


class JobOverview(BaseModel):
    total: int
    active: int
    archived: int


class ReviewCounts(BaseModel):
    approved: int
    pending: int
    rejected: int
    total: int


class SkillOverview(BaseModel):
    cv_extracted: ReviewCounts
    cv_added_manually: ReviewCounts
    job_extracted: ReviewCounts


class LinkCoverage(BaseModel):
    approved_skills: int
    approved_link: int
    pending_link: int
    no_link: int


class TaxonomyLinkOverview(BaseModel):
    cv: LinkCoverage
    job: LinkCoverage


class IndexCoverage(BaseModel):
    eligible: int
    indexed: int | None


class RetrievalIndexOverview(BaseModel):
    model_id: str
    model_revision: str
    template_version: str
    profiles: IndexCoverage
    jobs: IndexCoverage
    note: str


class SystemOverviewRead(BaseModel):
    generated_at: datetime
    taxonomy: TaxonomyOverview
    candidates: CandidateOverview
    jobs: JobOverview
    skills: SkillOverview
    taxonomy_links: TaxonomyLinkOverview
    retrieval_index: RetrievalIndexOverview

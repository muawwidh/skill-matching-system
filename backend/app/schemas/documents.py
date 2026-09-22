from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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

    model_config = {"from_attributes": True}


class JobSkillUpdate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=255)
    normalized_text: str = Field(min_length=1, max_length=255)
    skill_type: str = Field(default="skill", max_length=80)
    requirement_type: str = Field(default="unknown", max_length=50)
    evidence_sentence: str = ""
    review_status: str = Field(default="approved", max_length=50)


class CandidateJobMatchRead(BaseModel):
    id: UUID
    candidate_profile_id: UUID
    job_id: UUID
    score: float
    matched_required: list[str]
    matched_preferred: list[str]
    missing_required: list[str]
    missing_preferred: list[str]
    candidate_skill_count: int
    job_skill_count: int
    explanation: str
    job: JobRead

    model_config = {"from_attributes": True}

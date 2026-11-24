from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class CandidateProfileRead(BaseModel):
    id: UUID
    user_id: UUID
    headline: str
    summary: str
    consent_to_process_cv: bool
    status: str

    model_config = {"from_attributes": True}


class SkillStatusCounts(BaseModel):
    approved: int = 0
    pending: int = 0
    rejected: int = 0


class MatchingProfileCv(BaseModel):
    id: UUID
    original_filename: str
    source: str
    processed_at: datetime | None
    skills: SkillStatusCounts


class MatchingProfileRead(BaseModel):
    """What feeds the candidate's matching profile: all CVs plus manual skills.

    Only approved skills are used. `unattributed_skills` are extracted skills whose
    source CV term no longer exists (older rows); they still belong to the profile.
    """
    retrieval_status: str
    retrieval_message: str
    cvs: list[MatchingProfileCv]
    manual_skills: SkillStatusCounts
    unattributed_skills: SkillStatusCounts


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
    external_url: str = ""
    posted_at: datetime | None = None
    last_seen_at: datetime | None = None
    sections: list[SectionRead] = []

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def attribution(self) -> dict[str, str] | None:
        """Where a live job comes from; None for manual and evaluation jobs."""
        from app.job_sources.registry import ATTRIBUTION

        if self.source not in ATTRIBUTION:
            return None
        name, url = ATTRIBUTION[self.source]
        return {"name": name, "url": url}


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


class ManualSkillCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("The skill is required.")
        return value


class LanguageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2", "native"] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("The language is required.")
        return value


class LanguageRead(BaseModel):
    """A language on the candidate's profile; origin: added (by hand), cv (found in a CV), skill_editor."""
    id: UUID
    label: str
    name: str
    level: str | None = None
    status: str
    origin: str
    evidence: str = ""


class LanguageReview(BaseModel):
    decision: Literal["approved", "rejected"]


class LanguageEntryRead(BaseModel):
    label: str
    requirement: str
    reviewed: bool = True


class LanguageCoverageRead(BaseModel):
    """Job language requirements against the candidate's confirmed languages, by name only.

    `compared` is false when the candidate has no confirmed language; the job's languages
    are then listed as not assessed, with `note`. Never part of the order or the skill counts.
    """
    compared: bool = False
    matched: list[LanguageEntryRead] = []
    missing: list[LanguageEntryRead] = []
    note: str = ""


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
    # False: an automatically extracted job skill nobody reviewed (live jobs).
    reviewed: bool = True


class MissingSkillRead(BaseModel):
    label: str
    # Name-only checks cannot rule out the skill appearing under other wording.
    checked_via: Literal["taxonomy_concept", "skill_name"]
    reviewed: bool = True

    @model_validator(mode="before")
    @classmethod
    def _legacy_label(cls, value):
        # Older rows store a bare label; only concept-checked skills were stored that way.
        if isinstance(value, str):
            return {"label": value, "checked_via": "taxonomy_concept"}
        return value


class PartialSkillRead(BaseModel):
    """A job skill not matched, but sharing a direct ESCO broader skill/knowledge concept
    with one of the candidate's skills."""
    label: str
    broader_concept: str
    candidate_skill: str
    reviewed: bool = True


class JobCoverageRead(BaseModel):
    """Skill coverage of one job for the signed-in candidate, computed on read."""
    job_id: UUID
    matched_required: list[MatchedSkillRead]
    matched_preferred: list[MatchedSkillRead]
    missing_required: list[MissingSkillRead]
    missing_preferred: list[MissingSkillRead]
    partial_required: list[PartialSkillRead] = []
    partial_preferred: list[PartialSkillRead] = []
    candidate_skill_count: int
    job_skill_count: int
    explanation: str
    # Job terms of other kinds (qualification, experience, certification, ...): listed, never assessed.
    not_assessed_required: list[str] = []
    not_assessed_preferred: list[str] = []
    languages: LanguageCoverageRead = LanguageCoverageRead()
    job: JobRead


class SkillGapRead(BaseModel):
    label: str
    missing_in: int  # number of the top results that list this required skill as missing


class SkillGapsRead(BaseModel):
    """Most frequent required missing skills across the candidate's current top results (read-only)."""
    status: str
    of: int  # number of top results looked at (at most 10)
    gaps: list[SkillGapRead]


class JobPoolRead(BaseModel):
    """Live jobs the candidate's matches are searched in, and the last successful import."""
    live_jobs: int
    last_import_at: datetime | None


class JobOccupationRead(BaseModel):
    """The job title's ESCO occupation, or `determined: false` ("occupation not determined")."""
    determined: bool
    concept_id: UUID | None = None
    label: str | None = None
    isco_code: str | None = None
    isco_unit_group: str = ""


class RelatedExperienceRead(BaseModel):
    """Related experience for one job: explanation only, never part of the order."""
    relevant_months: int
    relevant_years: float
    isco_group: str
    isco_group_label: str
    min_required_years: int
    meets_requirement: bool


class RecommendationItem(BaseModel):
    """One retrieved job: its position in the top-N, explained by skill coverage."""
    rank: int
    job_id: UUID
    matched_required: list[MatchedSkillRead]
    matched_preferred: list[MatchedSkillRead]
    missing_required: list[MissingSkillRead]
    missing_preferred: list[MissingSkillRead]
    partial_required: list[PartialSkillRead] = []
    partial_preferred: list[PartialSkillRead] = []
    candidate_skill_count: int
    job_skill_count: int
    explanation: str
    # Job terms of other kinds (qualification, experience, certification, ...): listed, never assessed.
    not_assessed_required: list[str] = []
    not_assessed_preferred: list[str] = []
    languages: LanguageCoverageRead = LanguageCoverageRead()
    job: JobRead
    job_occupation: JobOccupationRead | None = None
    related_experience: RelatedExperienceRead | None = None
    # Minimum years the job text asks for (None: none stated); shown even when experience is not assessed.
    min_required_years: int | None = None


class RecommendationList(BaseModel):
    """Top-N retrieval result for the signed-in candidate.

    `status` is "ready" or the reason no retrieval was possible
    ("profile_not_ready", "no_approved_skills", "profile_not_indexed"); `results`
    is then empty. `unindexed_jobs` counts active jobs that cannot be retrieved
    because they have no current embedding. `total` is the number of retrieved
    jobs (at most `top_n`); `results` holds one page of them, each with
    its overall `rank`.
    """
    status: str
    message: str
    top_n: int
    total: int
    page: int
    page_size: int
    active_jobs: int
    unindexed_jobs: int
    # Related-experience filter: the remembered switch and how many jobs it hid
    # among the jobs considered for the top N.
    hide_below_experience: bool = False
    hidden_by_experience: int = 0
    has_work_entries_with_occupation: bool = False
    results: list[RecommendationItem]


class MatchPreferences(BaseModel):
    hide_below_experience: bool


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
    # Keys "manual", "evaluation", "live" (every non-manual, non-evaluation source).
    job_by_source: dict[str, ReviewCounts] = {}


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

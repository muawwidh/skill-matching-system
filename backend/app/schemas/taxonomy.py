from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TaxonomyVersionRead(BaseModel):
    id: UUID
    version: str
    release_date: str
    import_filename: str
    status: str
    is_sample: bool
    imported_at: datetime
    source_code: str
    source_name: str
    checksum: str
    import_report: dict = Field(default_factory=dict)


class TaxonomyConceptRead(BaseModel):
    id: UUID
    external_id: str
    preferred_label: str
    description: str
    concept_type: str
    language: str
    source_code: str
    taxonomy_version: str
    alternative_labels: list[str] = Field(default_factory=list)


class OccupationRead(BaseModel):
    id: UUID
    code: str
    title: str
    description: str
    job_zone: int | None
    source_code: str
    taxonomy_version: str


class EscoOnetMappingRead(BaseModel):
    id: UUID
    esco_concept_id: UUID
    esco_label: str
    onet_occupation_id: UUID
    onet_code: str
    onet_title: str
    mapping_type: str
    confidence_score: float
    source: str
    version: str


class TaxonomyImportResult(BaseModel):
    source_code: str
    version: str
    concepts_imported: int
    occupations_imported: int
    mappings_imported: int = 0
    is_sample: bool
    relationships_imported: int = 0
    structured_records_imported: int = 0
    import_report: dict = Field(default_factory=dict)


class TaxonomyRelationshipRead(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    taxonomy_version_id: UUID
    source_concept_id: UUID
    target_concept_id: UUID
    relationship_type: str
    metadata_json: dict


class OnetDataRecordRead(BaseModel):
    model_config = {"from_attributes": True}
    dataset: str
    occupation_code: str | None
    element_id: str
    scale_id: str
    task_id: str
    category: str
    numeric_value: Decimal | None
    source_data: dict


class TaxonomyLinkRequest(BaseModel):
    term_source: str = Field(pattern="^(candidate|job)$")
    document_id: UUID


class TaxonomyLinkCandidateRead(BaseModel):
    id: UUID
    term_source: str
    extracted_term_id: UUID
    raw_text: str
    normalized_text: str
    match_method: str
    confidence_score: float
    rank: int
    review_status: str
    concept: TaxonomyConceptRead


class TaxonomyLinkRunResult(BaseModel):
    terms_processed: int
    candidates_created: int
    links_auto_approved: int


class TaxonomyLinkReview(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    concept_id: UUID | None = None
    replace_selection: bool = False
    expected_selection_token: str | None = Field(default=None, max_length=64)


class TaxonomySelectionRead(BaseModel):
    candidate_id: UUID | None
    concept: TaxonomyConceptRead
    token: str


class TaxonomyReviewGroup(BaseModel):
    term_source: str
    extracted_term_id: UUID
    raw_text: str
    selection: TaxonomySelectionRead | None
    inconsistent: bool
    candidates: list[TaxonomyLinkCandidateRead]


class TaxonomyReviewPage(BaseModel):
    items: list[TaxonomyReviewGroup]
    has_more: bool


class TaxonomyReviewEventRead(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    candidate_id: UUID
    action: str
    reviewer_id: UUID | None
    created_at: datetime
    before_state: dict
    after_state: dict

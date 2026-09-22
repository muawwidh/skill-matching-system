from datetime import datetime
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

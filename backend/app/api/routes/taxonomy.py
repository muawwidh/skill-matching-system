from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_roles
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.taxonomy import (
    TaxonomyReviewEventRead,
    TaxonomyReviewPage,
    OnetDataRecordRead,
    TaxonomyRelationshipRead,
    EscoOnetMappingRead,
    OccupationRead,
    TaxonomyConceptRead,
    TaxonomyImportResult,
    TaxonomyLinkCandidateRead,
    TaxonomyLinkRequest,
    TaxonomyLinkReview,
    TaxonomyLinkRunResult,
    TaxonomyVersionRead,
)
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.packages import LIMITS


router = APIRouter()
taxonomy_admin = require_roles(settings.ADMIN_ROLE, settings.RESEARCHER_ROLE)


@router.get("/reviews", response_model=TaxonomyReviewPage)
def review_groups(
    state: str = Query("pending", pattern="^(pending|selected|all)$"),
    q: str = Query("", max_length=200), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    current_user: User = Depends(taxonomy_admin), db: Session = Depends(get_db),
) -> TaxonomyReviewPage:
    return TaxonomyService(db).review_groups(state, q, limit, offset)


@router.get("/reviews/{term_source}/{term_id}/history", response_model=list[TaxonomyReviewEventRead])
def review_history(
    term_id: UUID, term_source: str,
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    current_user: User = Depends(taxonomy_admin), db: Session = Depends(get_db),
) -> list[TaxonomyReviewEventRead]:
    if term_source not in {"candidate", "job"}:
        raise HTTPException(status_code=422, detail="Invalid term source.")
    return TaxonomyService(db).review_history(term_source, term_id, limit, offset)


@router.get("/concepts/{concept_id}/relationships", response_model=list[TaxonomyRelationshipRead])
def concept_relationships(
    concept_id: UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[TaxonomyRelationshipRead]:
    return TaxonomyService(db).relationships(concept_id, limit, offset)


@router.get("/occupations/{occupation_id}/data", response_model=list[OnetDataRecordRead])
def occupation_data(
    occupation_id: UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[OnetDataRecordRead]:
    return TaxonomyService(db).occupation_data(occupation_id, limit, offset)


def bounded_upload(file: UploadFile) -> bytes:
    content = file.file.read(LIMITS.upload + 1)
    if len(content) > LIMITS.upload:
        raise HTTPException(status_code=413, detail="Taxonomy upload exceeds 128 MiB limit.")
    return content


@router.get("/search", response_model=list[TaxonomyConceptRead])
def search_taxonomy(
    q: str = Query(min_length=2, max_length=200),
    source: str | None = None,
    concept_type: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxonomyConceptRead]:
    return TaxonomyService(db).search(q, source, concept_type, limit)


@router.get("/concepts/{concept_id}", response_model=TaxonomyConceptRead)
def get_concept(
    concept_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxonomyConceptRead:
    return TaxonomyService(db).get_concept(concept_id)


@router.get("/occupations/{occupation_id}", response_model=OccupationRead)
def get_occupation(
    occupation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OccupationRead:
    return TaxonomyService(db).get_occupation(occupation_id)


@router.get("/versions", response_model=list[TaxonomyVersionRead])
def list_versions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaxonomyVersionRead]:
    return TaxonomyService(db).list_versions()


@router.get("/mappings", response_model=list[EscoOnetMappingRead])
def list_mappings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EscoOnetMappingRead]:
    return TaxonomyService(db).list_mappings()


def import_taxonomy_release(
    source_code: str,
    file: UploadFile,
    version: str,
    release_date: str,
    db: Session,
) -> TaxonomyImportResult:
    return TaxonomyService(db).import_release(
        source_code=source_code,
        version=version,
        release_date=release_date,
        filename=file.filename or f"{source_code.lower()}-import.json",
        content=bounded_upload(file),
    )


@router.post("/import/esco", response_model=TaxonomyImportResult)
def import_esco(
    file: UploadFile = File(...),
    version: str = Form(...),
    release_date: str = Form(default=""),
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> TaxonomyImportResult:
    return import_taxonomy_release("ESCO", file, version, release_date, db)


@router.post("/import/onet", response_model=TaxonomyImportResult)
def import_onet(
    file: UploadFile = File(...),
    version: str = Form(...),
    release_date: str = Form(default=""),
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> TaxonomyImportResult:
    return import_taxonomy_release("ONET", file, version, release_date, db)


@router.post("/import/mappings", response_model=TaxonomyImportResult)
def import_mappings(
    file: UploadFile = File(...),
    version: str = Form(...),
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> TaxonomyImportResult:
    return TaxonomyService(db).import_mappings(
        version, file.filename or "esco-onet-mappings.json", bounded_upload(file)
    )


@router.post("/import/sample", response_model=list[TaxonomyImportResult])
def import_sample(
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> list[TaxonomyImportResult]:
    return TaxonomyService(db).import_bundled_sample()


@router.post("/link", response_model=TaxonomyLinkRunResult)
def link_terms(
    payload: TaxonomyLinkRequest,
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> TaxonomyLinkRunResult:
    return TaxonomyService(db).link_document(payload.term_source, payload.document_id)


@router.put("/link/{candidate_id}/approve", response_model=TaxonomyLinkCandidateRead)
def review_link(
    candidate_id: UUID,
    payload: TaxonomyLinkReview,
    current_user: User = Depends(taxonomy_admin),
    db: Session = Depends(get_db),
) -> TaxonomyLinkCandidateRead:
    return TaxonomyService(db).review_link(
        candidate_id, payload.status, payload.concept_id, current_user,
        payload.replace_selection, payload.expected_selection_token,
    )

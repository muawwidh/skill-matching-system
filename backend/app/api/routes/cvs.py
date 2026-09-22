from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import (
    CandidateSkillRead,
    CandidateSkillReviewRequest,
    CvDocumentRead,
    CvPasteRequest,
    SectionRead,
)
from app.services.cv_service import CvService
from app.services.skill_service import SkillService

router = APIRouter()


@router.post("/upload", response_model=CvDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    consent_to_process: bool = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvDocumentRead:
    return await CvService(db).upload_cv(current_user, file, consent_to_process)


@router.post("/paste", response_model=CvDocumentRead, status_code=status.HTTP_201_CREATED)
def paste_cv(
    payload: CvPasteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvDocumentRead:
    return CvService(db).paste_cv(current_user, payload)


@router.get("", response_model=list[CvDocumentRead])
def list_cvs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CvDocumentRead]:
    return CvService(db).list_my_cvs(current_user)


@router.get("/{document_id}", response_model=CvDocumentRead)
def get_cv(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvDocumentRead:
    return CvService(db).get_my_cv(current_user, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    CvService(db).delete_my_cv(current_user, document_id)


@router.post("/{document_id}/process", response_model=CvDocumentRead)
def process_cv(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CvDocumentRead:
    return CvService(db).process_cv(current_user, document_id)


@router.get("/{document_id}/sections", response_model=list[SectionRead])
def get_cv_sections(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SectionRead]:
    return CvService(db).get_my_cv(current_user, document_id).sections


@router.get("/{document_id}/extracted-skills", response_model=list[CandidateSkillRead])
def get_cv_extracted_skills(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CandidateSkillRead]:
    return SkillService(db).list_my_cv_skills(current_user, document_id)


@router.put("/{document_id}/extracted-skills", response_model=list[CandidateSkillRead])
def review_cv_extracted_skills(
    document_id: UUID,
    payload: CandidateSkillReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CandidateSkillRead]:
    CvService(db).get_my_cv(current_user, document_id)
    return SkillService(db).review_my_candidate_skills(current_user, payload)

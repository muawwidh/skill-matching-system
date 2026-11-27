from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import candidate_only, get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import (CandidateProfileRead, CandidateProfileUpdate, CandidateSkillRead, LanguageCreate,
                                   LanguageRead, LanguageReview, ManualSkillCreate, ManualSkillRead,
                                   MatchingProfileRead)
from app.schemas.experience import DetectedWorkEntryRead, OccupationSuggestionRead, WorkEntryRead, WorkEntryWrite
from app.services.candidate_service import CandidateService
from app.services.language_service import LanguageService
from app.services.skill_service import SkillService
from app.services.work_entry_service import WorkEntryService

router = APIRouter()


@router.get("/me", response_model=CandidateProfileRead)
def get_my_candidate_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CandidateProfileRead:
    return CandidateService(db).get_my_profile(current_user)


@router.put("/me", response_model=CandidateProfileRead)
def update_my_candidate_profile(
    payload: CandidateProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CandidateProfileRead:
    return CandidateService(db).update_my_profile(current_user, payload)


@router.get("/me/matching-profile", response_model=MatchingProfileRead)
def get_my_matching_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchingProfileRead:
    return CandidateService(db).my_matching_profile(current_user)


@router.get("/me/manual-skills", response_model=list[ManualSkillRead])
def my_manual_skills(current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    """Skills the candidate added by hand (not from a CV), with their ESCO area. Read-only."""
    return SkillService(db).my_manual_skills(current_user)


@router.post("/me/manual-skills", response_model=CandidateSkillRead, status_code=status.HTTP_201_CREATED)
def add_manual_skill(payload: ManualSkillCreate, current_user: User = Depends(candidate_only),
                     db: Session = Depends(get_db)):
    """Add a skill by hand. It stays until removed with DELETE; CV skill reviews never remove it."""
    return SkillService(db).add_my_manual_skill(current_user, payload.label)


@router.delete("/me/manual-skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_manual_skill(skill_id: UUID, current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    SkillService(db).remove_my_manual_skill(current_user, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Languages: compared with job language requirements by name; never used for ranking ---

def _language(service: LanguageService, user: User, skill_id: UUID) -> dict:
    return next(entry for entry in service.list_languages(user) if entry["id"] == skill_id)


@router.get("/me/languages", response_model=list[LanguageRead])
def my_languages(current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    return LanguageService(db).list_languages(current_user)


@router.post("/me/languages", response_model=LanguageRead, status_code=status.HTTP_201_CREATED)
def add_language(payload: LanguageCreate, current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    service = LanguageService(db)
    skill = service.add_language(current_user, payload.name, payload.level)
    return _language(service, current_user, skill.id)


@router.put("/me/languages/{skill_id}/review", response_model=LanguageRead)
def review_language(skill_id: UUID, payload: LanguageReview, current_user: User = Depends(candidate_only),
                    db: Session = Depends(get_db)):
    """Confirm or reject a language found in a CV."""
    service = LanguageService(db)
    skill = service.review_language(current_user, skill_id, payload.decision)
    if payload.decision == "rejected":
        return {"id": skill.id, "label": skill.raw_text, "name": skill.normalized_text, "level": None,
                "status": "rejected", "origin": "cv", "evidence": skill.evidence_sentence}
    return _language(service, current_user, skill.id)


@router.delete("/me/languages/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_language(skill_id: UUID, current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    LanguageService(db).remove_language(current_user, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Work entries for relevant experience: candidate accounts only ---------------------

@router.get("/me/work-entries", response_model=list[WorkEntryRead])
def list_my_work_entries(current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    return WorkEntryService(db).list_entries(current_user)


@router.get("/me/work-entries/detected", response_model=list[DetectedWorkEntryRead])
def detected_work_entries(current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    """Dated entries found in the candidate's CVs, to pre-fill the form. Nothing is stored."""
    return WorkEntryService(db).detected(current_user)


@router.get("/me/work-entries/occupation-suggestions", response_model=list[OccupationSuggestionRead])
def occupation_suggestions(title: str = Query("", max_length=255), current_user: User = Depends(candidate_only),
                           db: Session = Depends(get_db)):
    """Top 3 ESCO occupations for a job title; the candidate picks one or none."""
    return WorkEntryService(db).occupation_suggestions(title)


@router.post("/me/work-entries", response_model=WorkEntryRead, status_code=status.HTTP_201_CREATED)
def create_work_entry(payload: WorkEntryWrite, current_user: User = Depends(candidate_only),
                      db: Session = Depends(get_db)):
    return WorkEntryService(db).create(current_user, payload)


@router.put("/me/work-entries/{entry_id}", response_model=WorkEntryRead)
def update_work_entry(entry_id: UUID, payload: WorkEntryWrite, current_user: User = Depends(candidate_only),
                      db: Session = Depends(get_db)):
    return WorkEntryService(db).update(current_user, entry_id, payload)


@router.delete("/me/work-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_entry(entry_id: UUID, current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    WorkEntryService(db).delete(current_user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import candidate_only, get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import (CandidateProfileRead, CandidateProfileUpdate, CandidateSkillRead, ManualSkillCreate,
                                   MatchingProfileRead)
from app.schemas.experience import DetectedWorkEntryRead, OccupationSuggestionRead, WorkEntryRead, WorkEntryWrite
from app.services.candidate_service import CandidateService
from app.services.skill_service import MANUAL_SOURCE, SkillService
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


@router.get("/me/manual-skills", response_model=list[CandidateSkillRead])
def my_manual_skills(current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    """Skills the candidate added by hand (not from a CV). Read-only."""
    return [skill for skill in SkillService(db).list_my_candidate_skills(current_user) if skill.source == MANUAL_SOURCE]


@router.post("/me/manual-skills", response_model=CandidateSkillRead, status_code=status.HTTP_201_CREATED)
def add_manual_skill(payload: ManualSkillCreate, current_user: User = Depends(candidate_only),
                     db: Session = Depends(get_db)):
    """Add a skill by hand. It stays until removed with DELETE; CV skill reviews never remove it."""
    return SkillService(db).add_my_manual_skill(current_user, payload.label)


@router.delete("/me/manual-skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_manual_skill(skill_id: UUID, current_user: User = Depends(candidate_only), db: Session = Depends(get_db)):
    SkillService(db).remove_my_manual_skill(current_user, skill_id)
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

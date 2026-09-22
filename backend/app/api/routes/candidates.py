from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import CandidateProfileRead, CandidateProfileUpdate
from app.services.candidate_service import CandidateService

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

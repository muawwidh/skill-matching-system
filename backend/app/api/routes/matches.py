from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import CandidateJobMatchRead
from app.services.matching_service import MatchingService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/recommendations", response_model=list[CandidateJobMatchRead])
def list_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CandidateJobMatchRead]:
    return MatchingService(db).list_my_recommendations(current_user)


@router.post("/recommendations/refresh", response_model=list[CandidateJobMatchRead])
def refresh_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CandidateJobMatchRead]:
    return MatchingService(db).refresh_my_recommendations(current_user)


@router.post("/jobs/{job_id}", response_model=CandidateJobMatchRead)
def match_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CandidateJobMatchRead:
    return MatchingService(db).match_my_job(current_user, job_id)

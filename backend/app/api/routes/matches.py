"""Candidate job matching (D045, D049): computed on read, nothing stored per request."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import candidate_only
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import JobCoverageRead, MatchPreferences, RecommendationList
from app.services.matching_service import DEFAULT_PAGE_SIZE, PAGE_SIZES, MatchingService

router = APIRouter(dependencies=[Depends(candidate_only)])


def _page_size(page_size: int = Query(DEFAULT_PAGE_SIZE, description="10, 25 or 50")) -> int:
    if page_size not in PAGE_SIZES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"page_size must be one of {', '.join(map(str, PAGE_SIZES))}.")
    return page_size


@router.get("/recommendations", response_model=RecommendationList)
def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Depends(_page_size),
    current_user: User = Depends(candidate_only),
    db: Session = Depends(get_db),
) -> RecommendationList:
    return MatchingService(db).list_my_recommendations(current_user, page, page_size)


@router.post("/recommendations/refresh", response_model=RecommendationList)
def refresh_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Depends(_page_size),
    current_user: User = Depends(candidate_only),
    db: Session = Depends(get_db),
) -> RecommendationList:
    return MatchingService(db).refresh_my_recommendations(current_user, page, page_size)


@router.put("/preferences", response_model=MatchPreferences)
def update_match_preferences(
    payload: MatchPreferences,
    current_user: User = Depends(candidate_only),
    db: Session = Depends(get_db),
) -> MatchPreferences:
    """Remember the "hide jobs where my related experience is below the requirement" switch (D060)."""
    return MatchingService(db).set_hide_below_experience(current_user, payload.hide_below_experience)


@router.get("/jobs/{job_id}", response_model=JobCoverageRead)
def job_coverage(
    job_id: UUID,
    current_user: User = Depends(candidate_only),
    db: Session = Depends(get_db),
) -> JobCoverageRead:
    """Skill coverage of one active job for the signed-in candidate (no retrieval rank)."""
    return MatchingService(db).match_my_job(current_user, job_id)

from fastapi import APIRouter, Depends, Query
from typing import Literal
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.retrieval import RetrievedJob
from app.services.retrieval_service import RetrievalService

router = APIRouter()


@router.get("/jobs", response_model=list[RetrievedJob])
def retrieve_jobs(limit: int = Query(20, ge=1, le=100),
                  template_version: Literal["e5-job-profile-v1", "e5-job-profile-v2"] | None = None,
                  current_user: User = Depends(require_roles(settings.DEFAULT_CANDIDATE_ROLE)),
                  db: Session = Depends(get_db)) -> list[RetrievedJob]:
    return RetrievalService(db, template_version).jobs_for_user(current_user, limit)

"""Owner-only Phase 6 runs, separate from legacy /matches recommendations."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.matching_runs import CreateMatchingRun
from app.services.matching_runs_service import MatchingRunsService

router = APIRouter()
candidate = require_roles(settings.DEFAULT_CANDIDATE_ROLE)


@router.post("", status_code=201)
def create_run(payload: CreateMatchingRun, user: User = Depends(candidate), db: Session = Depends(get_db)):
    return MatchingRunsService(db).create(user)


@router.get("/current")
def current_run(user: User = Depends(candidate), db: Session = Depends(get_db)):
    return MatchingRunsService(db).current(user)


@router.get("/{run_id}")
def read_run(run_id: UUID, user: User = Depends(candidate), db: Session = Depends(get_db)):
    return MatchingRunsService(db).read(user, run_id)

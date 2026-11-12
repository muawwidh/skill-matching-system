"""Reviewed input management only; deliberately no run or score endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.matching_inputs import FactInput, GroupInput, InventoryInput, OccurrenceInput
from app.services.matching_inputs_service import MatchingInputsService

router = APIRouter()
candidate = require_roles(settings.DEFAULT_CANDIDATE_ROLE)
manager = require_roles(settings.ADMIN_ROLE, settings.RESEARCHER_ROLE)


def owned(db, user, profile_id):
    service = MatchingInputsService(db)
    if service.profile(user).id != profile_id:
        raise HTTPException(404, "Candidate profile not found")
    return service


@router.get("/candidates/{profile_id}/facts")
def candidate_facts(profile_id: UUID, user: User = Depends(candidate), db: Session = Depends(get_db)):
    return owned(db, user, profile_id).read_candidate(user)


@router.post("/candidates/{profile_id}/facts", status_code=201)
def add_candidate_fact(profile_id: UUID, payload: FactInput, user: User = Depends(candidate), db: Session = Depends(get_db)):
    return owned(db, user, profile_id).create_fact(user, payload)


@router.delete("/candidates/{profile_id}/facts/{fact_id}")
def remove_candidate_fact(profile_id: UUID, fact_id: UUID, expected_fingerprint: str = Query(pattern=r"^[0-9a-f]{64}$"),
                          user: User = Depends(candidate), db: Session = Depends(get_db)):
    return owned(db, user, profile_id).delete_fact(user, fact_id, expected_fingerprint)


@router.get("/jobs/{job_id}/inventory")
def job_inventory(job_id: UUID, user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).read_job(job_id)


@router.post("/jobs/{job_id}/facts", status_code=201)
def add_job_fact(job_id: UUID, payload: FactInput, user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).create_fact(user, payload, job_id)


@router.delete("/jobs/{job_id}/facts/{fact_id}")
def remove_job_fact(job_id: UUID, fact_id: UUID, expected_fingerprint: str = Query(pattern=r"^[0-9a-f]{64}$"),
                    user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).delete_fact(user, fact_id, expected_fingerprint, job_id)


@router.post("/jobs/{job_id}/groups", status_code=201)
def add_group(job_id: UUID, payload: GroupInput, user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).create_group(user, job_id, payload)


@router.delete("/jobs/{job_id}/groups/{group_id}")
def remove_group(job_id: UUID, group_id: UUID, expected_fingerprint: str = Query(pattern=r"^[0-9a-f]{64}$"),
                 user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).delete_group(user, job_id, group_id, expected_fingerprint)


@router.put("/jobs/{job_id}/occurrences/{skill_id}")
def classify(job_id: UUID, skill_id: UUID, payload: OccurrenceInput,
             user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).classify(user, job_id, skill_id, payload)


@router.put("/jobs/{job_id}/inventory")
def review_inventory(job_id: UUID, payload: InventoryInput, user: User = Depends(manager), db: Session = Depends(get_db)):
    return MatchingInputsService(db).signoff(user, job_id, payload)

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import JobCreate, JobRead, JobSkillRead, JobSkillUpdate, JobUpdate, SectionRead
from app.services.job_service import JobService
from app.services.skill_service import SkillService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobRead:
    return JobService(db).create_job(payload)


@router.post("/import", response_model=list[JobRead], status_code=status.HTTP_201_CREATED)
def import_jobs(payload: list[JobCreate], db: Session = Depends(get_db)) -> list[JobRead]:
    service = JobService(db)
    return [service.create_job(job) for job in payload]


@router.get("", response_model=list[JobRead])
def list_jobs(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[JobRead]:
    return JobService(db).list_jobs(include_archived=include_archived)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobRead:
    return JobService(db).get_job(job_id)


@router.put("/{job_id}", response_model=JobRead)
def update_job(job_id: UUID, payload: JobUpdate, db: Session = Depends(get_db)) -> JobRead:
    return JobService(db).update_job(job_id, payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: UUID, db: Session = Depends(get_db)) -> None:
    JobService(db).delete_job(job_id)


@router.post("/{job_id}/process", response_model=JobRead)
def process_job(job_id: UUID, db: Session = Depends(get_db)) -> JobRead:
    return JobService(db).process_job(job_id)


@router.post("/{job_id}/archive", response_model=JobRead)
def archive_job(job_id: UUID, db: Session = Depends(get_db)) -> JobRead:
    return JobService(db).archive_job(job_id)


@router.get("/{job_id}/sections", response_model=list[SectionRead])
def get_job_sections(job_id: UUID, db: Session = Depends(get_db)) -> list[SectionRead]:
    return JobService(db).get_job(job_id).sections


@router.get("/{job_id}/extracted-skills", response_model=list[JobSkillRead])
def get_job_extracted_skills(job_id: UUID, db: Session = Depends(get_db)) -> list[JobSkillRead]:
    return SkillService(db).list_job_skills(job_id)


@router.put("/{job_id}/extracted-skills/{skill_id}", response_model=JobSkillRead)
def update_job_extracted_skill(
    job_id: UUID,
    skill_id: UUID,
    payload: JobSkillUpdate,
    db: Session = Depends(get_db),
) -> JobSkillRead:
    return SkillService(db).update_job_skill(job_id, skill_id, payload)

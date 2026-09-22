from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Job
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import JobCreate, JobUpdate
from app.nlp.skill_extractor import SkillExtractor
from app.services.section_detection_service import SectionDetectionService
from app.services.text_cleaning_service import TextCleaningService


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.cleaner = TextCleaningService()
        self.section_detector = SectionDetectionService()
        self.skill_extractor = SkillExtractor()

    def create_job(self, payload: JobCreate) -> Job:
        cleaned_description = self.cleaner.clean(payload.description)
        job = self.repository.create_job(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            employment_type=payload.employment_type,
            description=payload.description,
            cleaned_description=cleaned_description,
        )
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_jobs(self, include_archived: bool = False) -> list[Job]:
        return self.repository.list_jobs(include_archived=include_archived)

    def get_job(self, job_id: UUID) -> Job:
        job = self.repository.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def update_job(self, job_id: UUID, payload: JobUpdate) -> Job:
        job = self.get_job(job_id)
        cleaned_description = self.cleaner.clean(payload.description)
        job = self.repository.update_job(
            job=job,
            title=payload.title,
            company=payload.company,
            location=payload.location,
            employment_type=payload.employment_type,
            description=payload.description,
            cleaned_description=cleaned_description,
            status=payload.status,
        )
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete_job(self, job_id: UUID) -> None:
        job = self.get_job(job_id)
        self.repository.delete_job(job)
        self.repository.add_processing_log("job", job_id, "deletion", "success", "Job deleted.")
        self.db.commit()

    def archive_job(self, job_id: UUID) -> Job:
        job = self.get_job(job_id)
        job.status = "archived"
        self.repository.add_processing_log("job", job.id, "archive", "success", "Job archived.")
        self.db.commit()
        self.db.refresh(job)
        return job

    def process_job(self, job_id: UUID) -> Job:
        job = self.get_job(job_id)
        job.cleaned_description = self.cleaner.clean(job.description)
        self._process_existing_job(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def _process_existing_job(self, job: Job) -> None:
        sections = self.section_detector.detect(job.cleaned_description)
        self.repository.replace_job_sections(job, sections)
        terms = self.skill_extractor.extract_from_sections(
            sections=sections,
            full_text=job.cleaned_description,
            document_kind="job",
        )
        self.repository.replace_job_terms(job, terms)
        job.status = "processed"
        job.error_message = ""
        job.processed_at = datetime.now(timezone.utc)
        self.repository.add_processing_log(
            "job",
            job.id,
            "document_processing",
            "success",
            f"Detected {len(sections)} job sections and {len(terms)} extracted terms.",
            {"section_count": len(sections), "term_count": len(terms)},
        )

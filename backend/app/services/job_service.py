from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Job
from app.repositories.document_repository import DocumentRepository
from app.schemas.documents import JobCreate, JobUpdate
from app.core.config import settings
from app.nlp.skill_extractor import ESCO_DIGITAL_SCHEME, EscoConceptLabels, EscoVocabulary, SkillExtractor
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.section_detection_service import SectionDetectionService, detect_job_segments
from app.services.text_cleaning_service import TextCleaningService
from app.services.taxonomy_service import TaxonomyService


_VOCABULARY_CACHE: dict[tuple, EscoVocabulary] = {}


def load_esco_vocabulary(db: Session) -> EscoVocabulary | None:
    """O7-filtered labels of the active, non-sample ESCO release, cached per release import."""
    repository = TaxonomyRepository(db)
    release = repository.esco_vocabulary_release()
    if release is None:
        return None
    key = (release.id, release.imported_at)
    if key not in _VOCABULARY_CACHE:
        concepts, labels = repository.esco_vocabulary_rows(release.id)
        labels_by_concept: dict[UUID, list[str]] = defaultdict(list)
        for concept_id, label in labels:
            labels_by_concept[concept_id].append(label)
        items = []
        for concept_id, concept_type, metadata, preferred_label in concepts:
            source = (metadata or {}).get("source", {})
            items.append(
                EscoConceptLabels(
                    concept_type=concept_type,
                    reuse_level=str(source.get("reuseLevel", "")),
                    digital=ESCO_DIGITAL_SCHEME in str(source.get("inScheme", "")),
                    labels=(preferred_label, *labels_by_concept[concept_id]),
                )
            )
        _VOCABULARY_CACHE.clear()
        _VOCABULARY_CACHE[key] = EscoVocabulary.from_concepts(items, f"ESCO-{release.version}")
    return _VOCABULARY_CACHE[key]


def build_job_extractor(db: Session, use_esco_vocabulary: bool | None = None) -> SkillExtractor:
    """Job extractor; the ESCO vocabulary follows JOB_EXTRACTION_ESCO_VOCABULARY unless overridden."""
    enabled = settings.JOB_EXTRACTION_ESCO_VOCABULARY if use_esco_vocabulary is None else use_esco_vocabulary
    return SkillExtractor(esco_vocabulary=load_esco_vocabulary(db) if enabled else None)


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.cleaner = TextCleaningService()
        self.section_detector = SectionDetectionService()
        self._skill_extractor: SkillExtractor | None = None

    @property
    def skill_extractor(self) -> SkillExtractor:
        if self._skill_extractor is None:
            self._skill_extractor = build_job_extractor(self.db)
        return self._skill_extractor

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
        from app.repositories.retrieval_repository import RetrievalRepository
        RetrievalRepository(self.db).invalidate_job(job.id)
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
        # Stored sections (display, retrieval input) keep the shared detector; extraction
        # uses the job requirement segmentation, which also drops benefits/EEO/application text.
        sections = self.section_detector.detect(job.cleaned_description)
        self.repository.replace_job_sections(job, sections)
        terms = self.skill_extractor.extract_from_sections(
            sections=detect_job_segments(job.cleaned_description),
            full_text=job.cleaned_description,
            document_kind="job",
        )
        self.repository.replace_job_terms(job, terms)
        TaxonomyService(self.db).link_document_if_taxonomy_available("job", job.id)
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

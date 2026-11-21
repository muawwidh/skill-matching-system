"""Import live jobs from public job APIs (DECISIONS.md D053, D055).

fetch -> strip contact details -> select (English, Europe/remote, newest-first cap)
-> dedupe by (source, external_id) and content hash -> existing job pipeline
(sections, extraction v3, taxonomy linking) -> archive unseen and over-cap live jobs
-> embed changed jobs in one batch.
"""
import logging
import threading
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.db.models import Job, ProcessingLog
from app.job_sources import NON_LIVE_SOURCES
from app.job_sources.base import FetchReport, JobPosting
from app.job_sources.http import JsonClient
from app.job_sources.selection import select_postings
from app.job_sources.text import content_hash, strip_contact_details
from app.repositories.document_repository import DocumentRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval import auto_reindex

log = logging.getLogger(__name__)

IMPORT_ENTITY = "job_import"
ARCHIVE_STAGE = "live_import_archive"
# One import at a time per process (CLI or admin button).
_run_lock = threading.Lock()


class ImportAlreadyRunning(RuntimeError):
    pass


def _live_filter():
    return Job.source.not_in(sorted(NON_LIVE_SOURCES))


class JobImportService:
    def __init__(self, db: Session, adapters: list, client: JsonClient, config: Settings = default_settings,
                 now: datetime | None = None, embed: bool | None = None) -> None:
        self.db = db
        self.adapters = adapters
        self.client = client
        self.config = config
        self.now = now or datetime.now(timezone.utc)
        self.embed = config.AUTO_REINDEX if embed is None else embed
        self.repository = DocumentRepository(db)

    # -- entry point -----------------------------------------------------------------------

    def run(self) -> dict:
        if not _run_lock.acquire(blocking=False):
            raise ImportAlreadyRunning("A job import is already running.")
        previous = self.db.info.get(auto_reindex.DISABLED_KEY)
        # Each job commits more than once in the pipeline; embed once at the end instead.
        self.db.info[auto_reindex.DISABLED_KEY] = True
        try:
            return self._run()
        finally:
            if previous is None:
                self.db.info.pop(auto_reindex.DISABLED_KEY, None)
            else:
                self.db.info[auto_reindex.DISABLED_KEY] = previous
            _run_lock.release()

    def _run(self) -> dict:
        run_id = uuid.uuid4()
        started = datetime.now(timezone.utc)
        fetched, fetch_reports = self._fetch()
        contacts = Counter()
        for posting in fetched:
            posting.description, removed = strip_contact_details(posting.description)
            contacts.update(removed)
        europe_only = frozenset(a.name for a in self.adapters if getattr(a, "europe_only", False))
        selected, selection = select_postings(
            fetched, self.config.LIVE_JOBS_MAX_ACTIVE, self.config.LIVE_JOBS_ENGLISH_ONLY,
            self.config.LIVE_JOBS_EUROPE_OR_REMOTE_ONLY, europe_only)

        outcomes: Counter = Counter()
        changed: set[UUID] = set()
        failures: list[str] = []
        for posting in selected:
            try:
                outcome, job_id = self._upsert(posting)
            except Exception as error:  # one bad posting must not stop the import
                self.db.rollback()
                outcome, job_id = "failed", None
                failures.append(f"{posting.source}:{posting.external_id}: {type(error).__name__}")
                log.warning("Live job import failed for %s:%s", posting.source, posting.external_id, exc_info=True)
            outcomes[outcome] += 1
            if job_id and outcome in {"created", "updated", "reactivated"}:
                changed.add(job_id)

        archived_unseen = self._archive(self._unseen_jobs(), "not_seen")
        archived_over_cap = self._archive(self._over_cap_jobs(), "over_cap")
        embedding = auto_reindex.reindex(self.db.get_bind(), set(), changed) if self.embed and changed else {}

        report = {
            "run_id": str(run_id),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "sources": {r.source: {"fetched": r.fetched, "requests": r.requests, "errors": r.errors}
                        for r in fetch_reports},
            "fetched": len(fetched),
            "contact_details_removed": dict(contacts),
            "skipped_language": dict(selection.skipped_language),
            "skipped_location": selection.skipped_location,
            "skipped_empty": selection.skipped_empty,
            "skipped_duplicate_id": selection.skipped_duplicate_id,
            "over_cap_not_imported": selection.over_cap,
            "selected": selection.selected,
            "outcomes": dict(outcomes),
            "failures": failures[:50],
            "archived_not_seen": archived_unseen,
            "archived_over_cap": archived_over_cap,
            "embedding": embedding,
            "active_live_jobs": self._active_live_count(),
        }
        self.repository.add_processing_log(IMPORT_ENTITY, run_id, "live_import", "success" if not failures else "partial",
                                           f"Imported live jobs: {dict(outcomes)}", report)
        self.db.commit()
        return report

    # -- steps -----------------------------------------------------------------------------

    def _fetch(self) -> tuple[list[JobPosting], list[FetchReport]]:
        postings: list[JobPosting] = []
        reports = []
        for adapter in self.adapters:
            report = FetchReport(adapter.name)
            postings.extend(adapter.fetch(self.client, report))
            reports.append(report)
        return postings, reports

    def _upsert(self, posting: JobPosting) -> tuple[str, UUID | None]:
        from app.services.job_service import JobService

        digest = content_hash(posting.title, posting.company, posting.description)
        job = self.db.scalar(select(Job).where(Job.source == posting.source,
                                               Job.external_id == posting.external_id))
        service = JobService(self.db)
        if job is None:
            duplicate = self.db.scalar(select(Job.id).where(Job.content_hash == digest, Job.status != "archived"))
            if duplicate:
                return "duplicate_content", None
            job = Job(source=posting.source, external_id=posting.external_id, status="draft")
            self._apply(job, posting, digest, service)
            self.db.add(job)
            self.db.flush()
            service._process_existing_job(job)
            self.db.commit()
            return "created", job.id

        job.last_seen_at = self.now
        if job.status == "archived":
            if not self._archived_by_import(job.id):
                self.db.commit()  # archived by staff: keep it archived
                return "kept_archived", job.id
            outcome = "reactivated"
        elif job.content_hash != digest:
            outcome = "updated"
        else:
            self.db.commit()
            return "unchanged", job.id
        self._apply(job, posting, digest, service)
        service._process_existing_job(job)  # additive re-extraction keeps reviews (D039)
        self.db.commit()
        return outcome, job.id

    def _apply(self, job: Job, posting: JobPosting, digest: str, service) -> None:
        job.title = posting.title[:255]
        job.company = posting.company[:255]
        job.location = posting.location[:255]
        job.employment_type = posting.employment_type[:80]
        job.description = posting.description
        job.cleaned_description = service.cleaner.clean(posting.description)
        job.external_url = posting.external_url[:1000]
        job.posted_at = posting.posted_at
        job.last_seen_at = self.now
        job.content_hash = digest

    def _archived_by_import(self, job_id: UUID) -> bool:
        last = self.db.scalar(select(ProcessingLog.stage).where(
            ProcessingLog.entity_type == "job", ProcessingLog.entity_id == job_id,
            ProcessingLog.stage.in_([ARCHIVE_STAGE, "archive"])).order_by(ProcessingLog.created_at.desc()).limit(1))
        return last == ARCHIVE_STAGE

    def _unseen_jobs(self) -> list[Job]:
        cutoff = self.now - timedelta(days=self.config.LIVE_JOBS_ARCHIVE_AFTER_DAYS)
        return list(self.db.scalars(select(Job).where(
            _live_filter(), Job.status != "archived",
            (Job.last_seen_at.is_(None)) | (Job.last_seen_at < cutoff))))

    def _over_cap_jobs(self) -> list[Job]:
        active = list(self.db.scalars(select(Job).where(_live_filter(), Job.status != "archived")))
        if len(active) <= self.config.LIVE_JOBS_MAX_ACTIVE:
            return []
        oldest = datetime.min.replace(tzinfo=timezone.utc)
        active.sort(key=lambda job: (job.posted_at or oldest, str(job.id)), reverse=True)
        return active[self.config.LIVE_JOBS_MAX_ACTIVE:]

    def _archive(self, jobs: list[Job], reason: str) -> int:
        retrieval = RetrievalRepository(self.db)
        for job in jobs:
            job.status = "archived"
            retrieval.invalidate_job(job.id)
            self.repository.add_processing_log("job", job.id, ARCHIVE_STAGE, "success",
                                               f"Live job archived ({reason}).", {"reason": reason})
        self.db.commit()
        return len(jobs)

    def _active_live_count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Job).where(_live_filter(), Job.status != "archived"))


def latest_import_runs(db: Session, limit: int = 5) -> list[dict]:
    rows = db.scalars(select(ProcessingLog).where(ProcessingLog.entity_type == IMPORT_ENTITY)
                      .order_by(ProcessingLog.created_at.desc()).limit(limit))
    return [{"status": row.status, "created_at": row.created_at, **row.metadata_json} for row in rows]


def is_import_running() -> bool:
    return _run_lock.locked()

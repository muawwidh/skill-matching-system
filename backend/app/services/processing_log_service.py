from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CandidateSkill, CvDocument, Job, JobSkill, ProcessingLog
from app.repositories.document_repository import DocumentRepository
from app.repositories.taxonomy_repository import TaxonomyRepository


class ProcessingLogService:
    def __init__(self, db: Session) -> None:
        self.repository = DocumentRepository(db)

    def list_logs(self, entity_type: str | None = None) -> list[ProcessingLog]:
        return self.repository.list_processing_logs(entity_type=entity_type)


def _review_counts(counts: dict[str, int]) -> dict[str, int]:
    return {"approved": counts.get("approved", 0), "pending": counts.get("pending", 0),
            "rejected": counts.get("rejected", 0), "total": sum(counts.values())}


class SystemOverviewService:
    """Read-only administrator overview of system-wide counts. Never writes."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.taxonomy = TaxonomyRepository(db)

    def overview(self) -> dict:
        from app.services.retrieval_service import RetrievalService

        jobs = self.documents.count_by(Job.status)
        cvs = self.documents.count_by(CvDocument.status)
        mappings = [{"esco_version": esco, "onet_version": onet, "rows": rows}
                    for esco, onet, rows in self.taxonomy.overview_mapping_counts()]
        return {
            "generated_at": datetime.now(timezone.utc),
            "taxonomy": {
                "releases": self._releases(),
                "esco_onet_mappings_total": sum(item["rows"] for item in mappings),
                "esco_onet_mappings": mappings,
            },
            "candidates": {
                "accounts": self.documents.count_users_with_role(settings.DEFAULT_CANDIDATE_ROLE),
                "cvs": {
                    "uploaded": sum(cvs.values()),
                    "processed": cvs.get("processed", 0),
                    "failed": cvs.get("failed", 0),
                    "failed_note": "Uploads that fail validation or parsing are rejected before storage "
                                   "and are not recorded, so this only counts stored CVs marked failed.",
                },
            },
            "jobs": {
                "total": sum(jobs.values()),
                "active": sum(count for status, count in jobs.items() if status != "archived"),
                "archived": jobs.get("archived", 0),
            },
            "skills": {
                "cv_extracted": _review_counts(self.documents.count_by(
                    CandidateSkill.review_status, CandidateSkill.source == "extraction")),
                "cv_added_manually": _review_counts(self.documents.count_by(
                    CandidateSkill.review_status, CandidateSkill.source != "extraction")),
                "job_extracted": _review_counts(self.documents.count_by(JobSkill.review_status)),
                # Split of job_extracted by job group; live "pending" is shown as "automatic" (D054).
                "job_by_source": {group: _review_counts(counts)
                                  for group, counts in self.documents.job_skill_counts_by_job_group().items()},
            },
            "taxonomy_links": {
                "cv": self.documents.taxonomy_link_coverage("candidate"),
                "job": self.documents.taxonomy_link_coverage("job"),
            },
            "retrieval_index": RetrievalService(self.db).index_overview(),
        }

    def _releases(self) -> list[dict]:
        releases: dict[tuple, dict] = {}
        for source, version, status, is_sample, concept_type, count in self.taxonomy.overview_concept_counts():
            release = releases.setdefault((source, version), {
                "source": source, "version": version, "status": status, "is_sample": is_sample,
                "skills": 0, "occupations": 0, "other": 0, "by_type": {},
            })
            if concept_type is None:  # release with no concepts
                continue
            release["by_type"][concept_type] = count
            bucket = {"skill": "skills", "occupation": "occupations"}.get(concept_type, "other")
            release[bucket] += count
        return list(releases.values())

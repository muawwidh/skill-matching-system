"""Relevant experience on the Jobs page (DECISIONS.md D060). Computed on read, never scored.

- Job occupation: the job title (cleaned) linked to an ESCO occupation with the
  existing automatic-approval rule; otherwise "occupation not determined".
  Manual and live jobs only; evaluation jobs are never linked.
- Relevance: a work entry is related to a job when both occupations are in the
  same 3-digit ISCO group; overlapping periods are merged.
"""
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Job
from app.job_sources import EVALUATION_SOURCE
from app.taxonomy.occupations import occupation_catalog

NOT_DETERMINED = {"determined": False, "concept_id": None, "label": None, "isco_code": None, "isco_unit_group": ""}


class ExperienceService:
    def __init__(self, db: Session, today: date | None = None) -> None:
        self.db = db
        self.today = today or datetime.now(timezone.utc).date()
        self._catalog = None

    @property
    def catalog(self):
        if self._catalog is None:
            self._catalog = occupation_catalog(self.db)
        return self._catalog

    def job_occupation(self, job: Job) -> dict:
        if job.source == EVALUATION_SOURCE:
            return dict(NOT_DETERMINED)
        link = self.catalog.link_job_title(job.title)
        if link.match is None:
            return dict(NOT_DETERMINED)
        return {"determined": True, **self.catalog.describe(link.match.concept_id)}

    def job_occupations(self, jobs: list[Job]) -> dict[UUID, dict]:
        return {job.id: self.job_occupation(job) for job in jobs}

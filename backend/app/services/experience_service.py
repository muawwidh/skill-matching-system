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
from app.matching.experience import RELEVANCE_DIGITS, WorkPeriod, isco_group, minimum_required_years, relevant_months
from app.repositories.work_entry_repository import WorkEntryRepository
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

    # -- relevance (item 5) -------------------------------------------------------------------

    def candidate_periods(self, profile_id: UUID) -> list[WorkPeriod]:
        """The candidate's work entries with a chosen occupation; "present" ends this month."""
        this_month = date(self.today.year, self.today.month, 1)
        periods = []
        for entry in WorkEntryRepository(self.db).list_entries(profile_id):
            code = self.catalog.isco_codes.get(entry.occupation_concept_id) if entry.occupation_concept_id else None
            if code:
                periods.append(WorkPeriod(entry.start_month, entry.end_month or this_month, code))
        return periods

    def relevant_months(self, periods: list[WorkPeriod], job_isco_code: str | None) -> int:
        """Merged months of the entries in the job's 3-digit ISCO group."""
        return relevant_months(periods, job_isco_code, RELEVANCE_DIGITS)

    def minimum_years(self, job: Job) -> int | None:
        if job.source == EVALUATION_SOURCE:
            return None
        return _minimum_years_cached(job.cleaned_description or job.description or "")

    def assess(self, job: Job, occupation: dict, periods: list[WorkPeriod]) -> dict | None:
        """Related experience for one job, or None when it cannot be shown.

        Shown only when the job has a minimum, the job occupation is determined
        and the candidate has at least one entry with an occupation.
        """
        minimum = self.minimum_years(job)
        if minimum is None or not occupation.get("determined") or not periods:
            return None
        group = isco_group(occupation["isco_code"])
        if group is None:
            return None
        months = self.relevant_months(periods, occupation["isco_code"])
        return {"relevant_months": months, "relevant_years": months // 6 / 2,  # whole half-years, rounded down
                "isco_group": group, "isco_group_label": self.catalog.group_label(group),
                "min_required_years": minimum, "meets_requirement": months >= minimum * 12}


_minimum_cache: dict[str, int | None] = {}


def _minimum_years_cached(text: str) -> int | None:
    """Minimum required years per job text, memoized by a digest of the text."""
    from hashlib import sha256

    key = sha256(text.encode()).hexdigest()
    if key not in _minimum_cache:
        if len(_minimum_cache) > 50_000:
            _minimum_cache.clear()
        _minimum_cache[key] = minimum_required_years(text)
    return _minimum_cache[key]

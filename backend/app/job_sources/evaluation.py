"""Tag the fixed evaluation job set as source=evaluation (D052)."""
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Job
from app.job_sources import EVALUATION_SOURCE, MANUAL_SOURCE

EXPECTED_EVALUATION_JOBS = 30


def evaluation_job_ids(mapping_path: Path) -> set[UUID]:
    """Read only the database job IDs from a mapping file.

    Accepts `{"jobs": {alias: "<uuid>"}}` (database-mapping) and
    `{"jobs": {alias: {"database_job_uuid": "<uuid>", ...}}}` (job-database-mapping).
    """
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    ids = [UUID(value["database_job_uuid"] if isinstance(value, dict) else value)
           for value in (mapping.get("jobs") or {}).values()]
    if len(ids) != len(set(ids)):
        raise ValueError("The mapping lists a database job more than once.")
    return set(ids)


def mark_evaluation_jobs(db: Session, job_ids: set[UUID], expected: int = EXPECTED_EVALUATION_JOBS) -> dict[str, int]:
    """Set source=evaluation on exactly these jobs; nothing else is changed.

    Refuses unless the set has `expected` jobs, all exist, and each is manual or
    already evaluation. Any other job previously tagged evaluation is set back
    to manual. Job text, skills, reviews and embeddings are untouched.
    """
    if len(job_ids) != expected:
        raise ValueError(f"Expected {expected} evaluation jobs, the mapping has {len(job_ids)}.")
    jobs = list(db.scalars(select(Job).where(Job.id.in_(job_ids))))
    if len(jobs) != len(job_ids):
        raise ValueError(f"{len(job_ids) - len(jobs)} mapped jobs do not exist in this database.")
    foreign = [job for job in jobs if job.source not in {MANUAL_SOURCE, EVALUATION_SOURCE}]
    if foreign:
        raise ValueError(f"{len(foreign)} mapped jobs come from a live source and cannot be evaluation jobs.")
    untagged = db.execute(update(Job).where(Job.source == EVALUATION_SOURCE, Job.id.not_in(job_ids))
                          .values(source=MANUAL_SOURCE)).rowcount
    tagged = sum(1 for job in jobs if job.source != EVALUATION_SOURCE)
    for job in jobs:
        job.source = EVALUATION_SOURCE
    db.flush()
    return {"evaluation_jobs": len(jobs), "newly_tagged": tagged, "untagged": untagged}

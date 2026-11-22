"""Tagging the fixed evaluation job set."""
import json

import pytest

from app.db.models import Job
from app.job_sources.evaluation import evaluation_job_ids, mark_evaluation_jobs


def make_job(db, source="manual"):
    job = Job(title="Job", description="x", cleaned_description="x", status="processed", source=source)
    db.add(job)
    db.flush()
    return job


def test_mapping_reads_only_job_ids(tmp_path):
    a, b = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"candidates": {"c1": "ignored"}, "jobs": {"j1": a, "j2": b}}))
    assert {str(x) for x in evaluation_job_ids(path)} == {a, b}
    path.write_text(json.dumps({"jobs": {"j1": {"database_job_uuid": a, "title": "ignored"},
                                         "j2": {"database_job_uuid": b}}}))
    assert {str(x) for x in evaluation_job_ids(path)} == {a, b}
    path.write_text(json.dumps({"jobs": {"j1": a, "j2": a}}))
    with pytest.raises(ValueError, match="more than once"):
        evaluation_job_ids(path)


def test_mark_evaluation_jobs_tags_exactly_the_set(db_session):
    first, second, other = make_job(db_session), make_job(db_session), make_job(db_session, "evaluation")
    description = first.description
    result = mark_evaluation_jobs(db_session, {first.id, second.id}, expected=2)
    assert result == {"evaluation_jobs": 2, "newly_tagged": 2, "untagged": 1}
    db_session.expire_all()
    assert (first.source, second.source, other.source) == ("evaluation", "evaluation", "manual")
    assert first.description == description
    # Idempotent.
    assert mark_evaluation_jobs(db_session, {first.id, second.id}, expected=2)["newly_tagged"] == 0


def test_mark_evaluation_jobs_refuses_wrong_sets(db_session):
    job, live = make_job(db_session), make_job(db_session, "arbeitnow")
    with pytest.raises(ValueError, match="Expected 2"):
        mark_evaluation_jobs(db_session, {job.id}, expected=2)
    import uuid
    with pytest.raises(ValueError, match="do not exist"):
        mark_evaluation_jobs(db_session, {job.id, uuid.uuid4()}, expected=2)
    with pytest.raises(ValueError, match="live source"):
        mark_evaluation_jobs(db_session, {job.id, live.id}, expected=2)

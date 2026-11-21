"""Live job import: dedupe, contact stripping, archiving, cap and isolation (D053, D055). No network."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Job, JobSkill, ProcessingLog, Role, User
from app.job_sources.arbeitnow import API_URL as ARBEITNOW_URL, ArbeitnowAdapter
from app.job_sources.greenhouse import API_URL as GREENHOUSE_URL, GreenhouseAdapter
from app.services import job_import_service
from app.services.job_import_service import ImportAlreadyRunning, JobImportService
from app.services.job_service import JobService
from tests.test_job_source_adapters import RecordedClient, fixture

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def responses(arbeitnow_p1=None, greenhouse=None):
    return {
        (ARBEITNOW_URL, (("page", 1),)): arbeitnow_p1 or fixture("arbeitnow_page1.json"),
        (ARBEITNOW_URL, (("page", 2),)): fixture("arbeitnow_page2.json"),
        (GREENHOUSE_URL.format(board="exampleco"), (("content", "true"),)): greenhouse or fixture("greenhouse_exampleco.json"),
    }


def run(db, client_responses=None, now=NOW, **config):
    adapters = [ArbeitnowAdapter(max_pages=5), GreenhouseAdapter(["exampleco"])]
    return JobImportService(db, adapters, RecordedClient(client_responses if client_responses is not None else responses()),
                            config=Settings(**config), now=now, embed=False).run()


def live_jobs(db):
    return {job.external_id: job for job in db.scalars(select(Job).where(Job.source.in_(["arbeitnow", "greenhouse"])))}


def test_first_import_creates_processed_jobs_and_strips_contacts(db_session):
    report = run(db_session)
    assert report["outcomes"] == {"created": 4}
    assert report["skipped_language"] == {"de": 2} and report["skipped_location"] == 2
    assert report["contact_details_removed"]["emails"] == 2
    assert report["active_live_jobs"] == 4
    jobs = live_jobs(db_session)
    assert set(jobs) == {"backend-engineer-berlin-1001", "support-specialist-remote-1003", "exampleco:5001", "exampleco:5005"}
    backend = jobs["backend-engineer-berlin-1001"]
    assert backend.source == "arbeitnow" and backend.status == "processed"
    assert backend.external_url.startswith("https://www.arbeitnow.com/jobs/")
    assert backend.posted_at is not None and backend.last_seen_at is not None and len(backend.content_hash) == 64
    for text in (backend.description, backend.cleaned_description, jobs["exampleco:5001"].description):
        assert "@" not in text and "Jane" not in text and "Mustermann" not in text and "1234 5678" not in text
    # The existing pipeline ran: extracted skills are stored, pending review.
    skills = list(db_session.scalars(select(JobSkill).where(JobSkill.job_id == backend.id)))
    assert {"python", "postgresql", "docker"} <= {skill.normalized_text for skill in skills}
    assert {skill.review_status for skill in skills} == {"pending"}
    log = db_session.scalar(select(ProcessingLog).where(ProcessingLog.entity_type == "job_import"))
    assert log.metadata_json["outcomes"] == {"created": 4}


def test_reimport_is_idempotent_and_updates_changed_postings(db_session):
    run(db_session)
    later = NOW + timedelta(days=1)
    assert run(db_session, now=later)["outcomes"] == {"unchanged": 4}
    assert all(job.last_seen_at.replace(tzinfo=timezone.utc) == later for job in live_jobs(db_session).values())

    page = copy.deepcopy(fixture("arbeitnow_page1.json"))
    page["data"][0]["description"] += "<p>Kubernetes experience is a plus.</p>"
    report = run(db_session, responses(arbeitnow_p1=page), now=later)
    assert report["outcomes"] == {"updated": 1, "unchanged": 3}
    job = live_jobs(db_session)["backend-engineer-berlin-1001"]
    assert "Kubernetes" in job.description
    assert db_session.scalar(select(Job.id).where(Job.external_id == "backend-engineer-berlin-1001")) == job.id


def test_same_posting_under_another_id_is_a_content_duplicate(db_session):
    page = copy.deepcopy(fixture("arbeitnow_page1.json"))
    copy_of_first = copy.deepcopy(page["data"][0])
    copy_of_first["slug"] = "backend-engineer-berlin-1001-repost"
    page["data"].append(copy_of_first)
    report = run(db_session, responses(arbeitnow_p1=page))
    assert report["outcomes"] == {"created": 4, "duplicate_content": 1}
    ids = set(live_jobs(db_session))
    assert len(ids & {"backend-engineer-berlin-1001", "backend-engineer-berlin-1001-repost"}) == 1 and len(ids) == 4


def test_unseen_jobs_are_archived_and_come_back_when_seen_again(db_session):
    run(db_session)
    staff_archived = live_jobs(db_session)["exampleco:5001"]
    JobService(db_session).archive_job(staff_archived.id)
    manual = JobService(db_session).repository.create_job("Manual role", "", "", "", "Python", "Python")
    evaluation = Job(title="Evaluation role", description="x", cleaned_description="x", status="processed",
                     source="evaluation")
    db_session.add(evaluation)
    db_session.commit()

    # Sources return nothing for longer than the archive window.
    report = run(db_session, client_responses={}, now=NOW + timedelta(days=15), LIVE_JOBS_ARCHIVE_AFTER_DAYS=14)
    assert report["archived_not_seen"] == 3 and report["active_live_jobs"] == 0
    assert report["sources"]["arbeitnow"]["errors"]
    db_session.expire_all()
    assert manual.status == "processed" and evaluation.status == "processed"

    report = run(db_session, now=NOW + timedelta(days=16))
    assert report["outcomes"] == {"reactivated": 3, "kept_archived": 1}
    jobs = live_jobs(db_session)
    assert jobs["exampleco:5001"].status == "archived"  # archived by staff stays archived
    assert jobs["backend-engineer-berlin-1001"].status == "processed"


def test_recently_seen_jobs_survive_a_failed_fetch(db_session):
    run(db_session)
    report = run(db_session, client_responses={}, now=NOW + timedelta(days=2), LIVE_JOBS_ARCHIVE_AFTER_DAYS=14)
    assert report["archived_not_seen"] == 0 and report["active_live_jobs"] == 4


def test_cap_keeps_the_newest_live_jobs(db_session):
    report = run(db_session, LIVE_JOBS_MAX_ACTIVE=2)
    assert report["over_cap_not_imported"] == 2 and report["outcomes"] == {"created": 2}
    assert set(live_jobs(db_session)) == {"support-specialist-remote-1003", "backend-engineer-berlin-1001"}
    # Lowering the cap later archives the oldest active live jobs.
    report = run(db_session, now=NOW + timedelta(hours=1), LIVE_JOBS_MAX_ACTIVE=1)
    assert report["archived_over_cap"] == 1 and report["active_live_jobs"] == 1
    assert live_jobs(db_session)["support-specialist-remote-1003"].status == "processed"


def test_only_one_import_runs_at_a_time(db_session):
    assert job_import_service._run_lock.acquire(blocking=False)
    try:
        with pytest.raises(ImportAlreadyRunning):
            run(db_session)
    finally:
        job_import_service._run_lock.release()


def _headers(client, db_session, email, role=None):
    response = client.post("/auth/register", json={"email": email, "full_name": "Synthetic", "password": "correct-horse-password"})
    if role:
        user = db_session.scalar(select(User).where(User.email == email))
        user.roles.append(db_session.scalar(select(Role).where(Role.name == role)) or Role(name=role, description=""))
        db_session.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_run_import_endpoint_is_admin_only(client, db_session, monkeypatch):
    started = []
    monkeypatch.setattr("app.api.routes.admin._run_import_in_background", lambda: started.append(True))
    for email, role in (("candidate@example.com", None), ("researcher@example.com", "researcher")):
        headers = _headers(client, db_session, email, role)
        assert client.post("/admin/job-import", headers=headers).status_code == 403
        assert client.get("/admin/job-import", headers=headers).status_code == 403
    admin = _headers(client, db_session, "admin@example.com", "admin")
    assert client.post("/admin/job-import", headers=admin).status_code == 202 and started == [True]
    run(db_session)
    body = client.get("/admin/job-import", headers=admin).json()
    assert body["running"] is False and body["runs"][0]["outcomes"] == {"created": 4}


def test_changed_jobs_are_embedded_once_at_the_end(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(job_import_service.auto_reindex, "reindex",
                        lambda bind, profiles, jobs: calls.append((set(profiles), set(jobs))) or {"indexed": len(jobs)})
    adapters = [ArbeitnowAdapter(max_pages=5), GreenhouseAdapter(["exampleco"])]
    report = JobImportService(db_session, adapters, RecordedClient(responses()), config=Settings(), now=NOW,
                              embed=True).run()
    assert calls == [(set(), {job.id for job in live_jobs(db_session).values()})]
    assert report["embedding"] == {"indexed": 4}
    # Nothing changed: no embedding call.
    JobImportService(db_session, adapters, RecordedClient(responses()), config=Settings(), now=NOW, embed=True).run()
    assert len(calls) == 1
    assert auto_reindex_disabled_key_cleared(db_session)


def auto_reindex_disabled_key_cleared(db_session) -> bool:
    from app.retrieval.auto_reindex import DISABLED_KEY
    return DISABLED_KEY not in db_session.info

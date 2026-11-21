"""Evaluation jobs stay out of the candidate Jobs page; evaluation runs search only them (D056)."""
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Job, Role, User
from app.job_sources import candidate_excluded_sources
from app.services.job_service import JobService


def _job(db, source, title):
    job = Job(title=title, description="Requirements\n- Python", cleaned_description="Requirements\n- Python",
              status="draft", source=source)
    db.add(job)
    db.flush()
    JobService(db)._process_existing_job(job)
    db.commit()
    return job


def _candidate(client):
    response = client.post("/auth/register", json={"email": "candidate@example.com", "full_name": "Synthetic",
                                                   "password": "correct-horse-password"})
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    cv = client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython", "original_filename": "cv.txt", "consent_to_process": True}).json()
    skills = client.get(f"/cvs/{cv['id']}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = "approved"
    client.put(f"/cvs/{cv['id']}/extracted-skills", headers=headers, json={"skills": skills})
    return headers


def test_candidate_view_excludes_evaluation_jobs_by_default(client, db_session, fake_retrieval, monkeypatch):
    evaluation = _job(db_session, "evaluation", "Evaluation role")
    manual = _job(db_session, "manual", "Manual role")
    live = _job(db_session, "greenhouse", "Live role")
    headers = _candidate(client)

    body = client.get("/matches/recommendations", headers=headers).json()
    assert {item["job_id"] for item in body["results"]} == {str(manual.id), str(live.id)}
    assert body["active_jobs"] == 2
    assert client.get(f"/matches/jobs/{evaluation.id}", headers=headers).status_code == 404
    assert client.get(f"/matches/jobs/{live.id}", headers=headers).status_code == 200

    monkeypatch.setattr(settings, "CANDIDATE_VIEW_INCLUDES_EVALUATION_JOBS", True)
    assert candidate_excluded_sources() == frozenset()
    body = client.get("/matches/recommendations", headers=headers).json()
    assert {UUID(item["job_id"]) for item in body["results"]} == {evaluation.id, manual.id, live.id}
    assert client.get(f"/matches/jobs/{evaluation.id}", headers=headers).status_code == 200


def test_staff_still_see_every_job(client, db_session):
    _job(db_session, "evaluation", "Evaluation role")
    _job(db_session, "arbeitnow", "Live role")
    response = client.post("/auth/register", json={"email": "admin@example.com", "full_name": "Synthetic",
                                                   "password": "correct-horse-password"})
    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    user.roles.append(Role(name="admin", description=""))
    db_session.commit()
    jobs = client.get("/jobs", headers={"Authorization": f"Bearer {response.json()['access_token']}"}).json()
    assert {job["source"] for job in jobs} == {"evaluation", "arbeitnow"}


def test_candidates_do_not_see_evaluation_jobs_in_the_job_list(client, db_session):
    evaluation = _job(db_session, "evaluation", "Evaluation role")
    live = _job(db_session, "arbeitnow", "Live role")
    headers = _candidate(client)
    assert {job["id"] for job in client.get("/jobs", headers=headers).json()} == {str(live.id)}
    assert client.get(f"/jobs/{evaluation.id}", headers=headers).status_code == 404
    assert client.get(f"/jobs/{live.id}", headers=headers).status_code == 200

"""Jobs page recommendations: top-N retrieval, explained by skill coverage (D045)."""
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Role, User


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={
        "email": email, "full_name": "Synthetic User", "password": "correct-horse-password"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def manager(client: TestClient, db_session: Session) -> dict[str, str]:
    headers = register(client, "manager@example.com")
    user = db_session.scalar(select(User).where(User.email == "manager@example.com"))
    user.roles.append(Role(name="admin", description="Job management"))
    db_session.commit()
    return headers


def candidate_with_skills(client: TestClient, email: str = "candidate@example.com") -> dict[str, str]:
    headers = register(client, email)
    cv = client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython\nFastAPI", "original_filename": "cv.txt", "consent_to_process": True})
    assert cv.status_code == 201
    skills = client.get(f"/cvs/{cv.json()['id']}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = "approved"
    assert client.put(f"/cvs/{cv.json()['id']}/extracted-skills", headers=headers,
                      json={"skills": skills}).status_code == 200
    return headers


def create_job(client: TestClient, headers: dict[str, str], title: str, required: str) -> str:
    response = client.post("/jobs", headers=headers, json={
        "title": title, "company": "Acme", "location": "", "employment_type": "",
        "description": f"Required skills\n{required}"})
    assert response.status_code == 201
    job_id = response.json()["id"]
    for skill in client.get(f"/jobs/{job_id}/extracted-skills", headers=headers).json():
        skill["review_status"] = "approved"
        assert client.put(f"/jobs/{job_id}/extracted-skills/{skill['id']}", headers=headers,
                          json=skill).status_code == 200
    return job_id


def test_order_is_retrieval_order_and_coverage_only_explains(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    full = create_job(client, staff, "Full coverage", "Python")
    none = create_job(client, staff, "No coverage", "Docker")
    headers = candidate_with_skills(client)
    fake_retrieval["order"] = [UUID(none), UUID(full)]

    body = client.get("/matches/recommendations", headers=headers).json()
    assert body["status"] == "ready"
    assert [(item["rank"], item["job_id"]) for item in body["results"]] == [(1, none), (2, full)]
    # Coverage is reported but does not reorder: the fully covered job stays second.
    assert body["results"][1]["matched_required"] == [{"label": "python", "matched_via": "skill_name"}]
    assert body["results"][0]["matched_required"] == []


def test_results_are_cut_to_top_n_and_unindexed_jobs_are_counted(client, db_session, fake_retrieval, monkeypatch):

    staff = manager(client, db_session)
    ids = [UUID(create_job(client, staff, f"Job {n}", "Python")) for n in range(3)]
    headers = candidate_with_skills(client)
    monkeypatch.setattr(settings, "RECOMMENDATION_TOP_N", 2)
    fake_retrieval["order"] = ids
    fake_retrieval["fresh"] = ids[:2]  # the third job has no current vector

    body = client.get("/matches/recommendations", headers=headers).json()
    assert body["top_n"] == 2 and body["active_jobs"] == 3 and body["unindexed_jobs"] == 1
    assert [item["rank"] for item in body["results"]] == [1, 2]
    assert [item["job_id"] for item in body["results"]] == [str(ids[0]), str(ids[1])]


def test_profile_without_embedding_gets_a_notice_and_no_results(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    create_job(client, staff, "Job", "Python")
    headers = candidate_with_skills(client)
    fake_retrieval["indexed_profile"] = False

    body = client.get("/matches/recommendations", headers=headers).json()
    assert body["status"] == "profile_not_indexed" and body["results"] == []
    assert "no up-to-date embedding" in body["message"]


def test_candidate_without_cv_is_not_ready(client, fake_retrieval):
    headers = register(client, "new@example.com")
    body = client.get("/matches/recommendations", headers=headers).json()
    assert body["status"] == "profile_not_ready" and body["results"] == []
    assert body["message"]


def test_missing_model_artifacts_report_retrieval_unavailable(client, db_session, fake_retrieval, monkeypatch):
    from app.services.retrieval_service import RetrievalService

    staff = manager(client, db_session)
    create_job(client, staff, "Job", "Python")
    headers = candidate_with_skills(client)

    def unavailable(self, query, limit):
        raise RuntimeError("Pinned local tokenizer unavailable")

    monkeypatch.setattr(RetrievalService, "retrieve", unavailable)
    body = client.get("/matches/recommendations", headers=headers).json()
    assert body["status"] == "retrieval_unavailable" and body["results"] == []

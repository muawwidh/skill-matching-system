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


# --- D049: candidate accounts only, computed on read -------------------------------


def row_counts(db_session: Session) -> dict[str, int]:
    from sqlalchemy import func

    from app.db.base import Base
    db_session.expire_all()
    return {name: db_session.scalar(select(func.count()).select_from(table))
            for name, table in Base.metadata.tables.items()}


def test_matches_are_computed_on_read_without_storing_rows(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    job_id = create_job(client, staff, "Python role", "Python")
    archived = create_job(client, staff, "Old role", "Python")
    assert client.post(f"/jobs/{archived}/archive", headers=staff).status_code in {200, 204}
    headers = candidate_with_skills(client)
    fake_retrieval["indexed_profile"] = True

    client.get("/matches/recommendations", headers=headers)  # creates the profile row if missing
    before = row_counts(db_session)
    for _ in range(2):
        body = client.get("/matches/recommendations", headers=headers).json()
        assert [item["job_id"] for item in body["results"]] == [job_id]
    coverage = client.get(f"/matches/jobs/{job_id}", headers=headers)
    assert coverage.status_code == 200
    assert coverage.json()["matched_required"] == [{"label": "python", "matched_via": "skill_name"}]
    assert "score" not in coverage.json() and "rank" not in coverage.json()
    assert client.get(f"/matches/jobs/{archived}", headers=headers).status_code == 404
    assert row_counts(db_session) == before
    assert "candidate_job_matches" not in before  # dropped in migration 0009
    assert client.post("/matches/recommendations/refresh", headers=headers).status_code == 200
    # The former write endpoint is gone.
    assert client.post(f"/matches/jobs/{job_id}", headers=headers).status_code == 405


def test_matches_are_candidate_only(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    job_id = create_job(client, staff, "Python role", "Python")
    researcher = register(client, "researcher@example.com")
    user = db_session.scalar(select(User).where(User.email == "researcher@example.com"))
    user.roles.append(db_session.scalar(select(Role).where(Role.name == "researcher"))
                      or Role(name="researcher", description=""))
    db_session.commit()
    for headers in (staff, researcher):
        assert client.get("/matches/recommendations", headers=headers).status_code == 403
        assert client.post("/matches/recommendations/refresh", headers=headers).status_code == 403
        assert client.get(f"/matches/jobs/{job_id}", headers=headers).status_code == 403
    assert client.get("/matches/recommendations").status_code == 401
    # A user without the candidate role is refused too.
    plain = register(client, "plain@example.com")
    user = db_session.scalar(select(User).where(User.email == "plain@example.com"))
    user.roles.clear()
    db_session.commit()
    assert client.get("/matches/recommendations", headers=plain).status_code == 403

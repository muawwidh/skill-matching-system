import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Role, User


JOB = {
    "title": "Synthetic API Engineer",
    "company": "Test Organization",
    "location": "Remote",
    "employment_type": "Full-time",
    "description": "Required skills\nPython\nSQL",
}


def headers_for(client: TestClient, db: Session, role: str, suffix: str) -> dict[str, str]:
    email = f"{role}-{suffix}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "full_name": "Synthetic User", "password": "correct-horse-password"},
    )
    assert response.status_code == 201
    if role != "candidate":
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.roles.append(db.scalar(select(Role).where(Role.name == role)) or Role(name=role, description=f"{role} access"))
        db.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def request_for(operation: str, job_id: str, skill_id: str) -> tuple[str, str, dict]:
    if operation == "create":
        return "post", "/jobs", {"json": JOB}
    if operation == "import":
        return "post", "/jobs/import", {"json": [JOB]}
    if operation == "update":
        return "put", f"/jobs/{job_id}", {"json": {**JOB, "title": "Updated", "status": "processed"}}
    if operation == "process":
        return "post", f"/jobs/{job_id}/process", {}
    if operation == "edit_skill":
        return "put", f"/jobs/{job_id}/extracted-skills/{skill_id}", {
            "json": {
                "raw_text": "Java", "normalized_text": "java", "skill_type": "skill",
                "requirement_type": "required", "evidence_sentence": "Python", "review_status": "approved",
            },
        }
    if operation == "archive":
        return "post", f"/jobs/{job_id}/archive", {}
    if operation == "delete":
        return "delete", f"/jobs/{job_id}", {}
    raise AssertionError(operation)


@pytest.mark.parametrize("operation", ["create", "import", "update", "process", "edit_skill", "archive", "delete"])
@pytest.mark.parametrize("role", [None, "candidate", "admin", "researcher"])
def test_job_mutation_permission_matrix(
    client: TestClient, db_session: Session, operation: str, role: str | None,
) -> None:
    admin_headers = headers_for(client, db_session, "admin", "seed")
    seeded = client.post("/jobs", headers=admin_headers, json=JOB)
    assert seeded.status_code == 201
    job_id = seeded.json()["id"]
    skills = client.get(f"/jobs/{job_id}/extracted-skills", headers=admin_headers)
    assert skills.status_code == 200 and skills.json()
    skill_id = skills.json()[0]["id"]

    headers = headers_for(client, db_session, role, "actor") if role else {}
    method, path, kwargs = request_for(operation, job_id, skill_id)
    response = getattr(client, method)(path, headers=headers, **kwargs)
    expected = 401 if role is None else 403 if role == "candidate" else 204 if operation == "delete" else 201 if operation in {"create", "import"} else 200
    assert response.status_code == expected, response.text
    if operation == "edit_skill" and role in {"admin", "researcher"}:
        assert response.json()["raw_text"] == "Java"
    if operation == "edit_skill" and role == "candidate":
        assert client.get(f"/jobs/{job_id}/extracted-skills", headers=headers).json()[0]["raw_text"] != "Java"

    if role == "candidate":
        for read_path in ("/jobs", f"/jobs/{job_id}", f"/jobs/{job_id}/sections", f"/jobs/{job_id}/extracted-skills"):
            assert client.get(read_path, headers=headers).status_code == 200
    if role in {"admin", "researcher"}:
        assert {item["name"] for item in client.get("/auth/me", headers=headers).json()["roles"]} == {"candidate", role}


OVERVIEW_KEYS = {"generated_at", "taxonomy", "candidates", "jobs", "skills", "taxonomy_links", "retrieval_index"}


def test_admin_overview_returns_counts(client: TestClient, db_session: Session) -> None:
    candidate = headers_for(client, db_session, "candidate", "overview")
    admin = headers_for(client, db_session, "admin", "overview")
    assert client.post("/cvs/paste", headers=candidate, json={
        "text": "Skills\nPython\nSQL", "original_filename": "cv.txt", "consent_to_process": True,
    }).status_code == 201
    created = client.post("/jobs", headers=admin, json=JOB)
    assert created.status_code == 201
    assert client.post("/jobs", headers=admin, json={**JOB, "title": "Archived role"}).status_code == 201
    archived_id = client.get("/jobs", headers=admin).json()
    archived_id = next(item["id"] for item in archived_id if item["title"] == "Archived role")
    assert client.post(f"/jobs/{archived_id}/archive", headers=admin).status_code in {200, 204}

    response = client.get("/admin/overview", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == OVERVIEW_KEYS
    assert set(body["taxonomy"]) == {"releases", "esco_onet_mappings_total", "esco_onet_mappings"}
    assert body["taxonomy"]["releases"] == [] and body["taxonomy"]["esco_onet_mappings_total"] == 0
    expected_accounts = db_session.scalar(
        select(func.count(func.distinct(User.id))).join(User.roles).where(Role.name == "candidate"))
    assert body["candidates"]["accounts"] == expected_accounts
    cvs = body["candidates"]["cvs"]
    assert (cvs["uploaded"], cvs["processed"], cvs["failed"]) == (1, 1, 0) and cvs["failed_note"]
    assert body["jobs"] == {"total": 2, "active": 1, "archived": 1}
    cv_skills = body["skills"]["cv_extracted"]
    assert cv_skills["total"] >= 2 and cv_skills["pending"] == cv_skills["total"]
    assert body["skills"]["cv_added_manually"]["total"] == 0
    assert body["skills"]["job_extracted"]["pending"] == body["skills"]["job_extracted"]["total"] >= 4
    # Split by job group; jobs created through the API are manual.
    by_source = body["skills"]["job_by_source"]
    assert set(by_source) == {"manual", "evaluation", "live"}
    assert by_source["manual"] == body["skills"]["job_extracted"]
    assert by_source["evaluation"]["total"] == by_source["live"]["total"] == 0
    # No approved skills yet, so nothing can carry a link and no profile is eligible for indexing.
    assert body["taxonomy_links"]["cv"] == {"approved_skills": 0, "approved_link": 0, "pending_link": 0, "no_link": 0}
    index = body["retrieval_index"]
    assert set(index) == {"model_id", "model_revision", "template_version", "profiles", "jobs", "note"}
    assert index["profiles"] == {"eligible": 0, "indexed": 0}
    assert index["jobs"] == {"eligible": 1, "indexed": 0}
    assert "%" not in response.text


def test_admin_overview_link_coverage_counts_approved_skills(client: TestClient, db_session: Session) -> None:
    candidate = headers_for(client, db_session, "candidate", "links")
    admin = headers_for(client, db_session, "admin", "links")
    cv_id = client.post("/cvs/paste", headers=candidate, json={
        "text": "Skills\nPython\nSQL", "original_filename": "cv.txt", "consent_to_process": True,
    }).json()["id"]
    skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=candidate).json()
    skills[0]["review_status"] = "approved"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=candidate, json={"skills": skills}).status_code == 200

    body = client.get("/admin/overview", headers=admin).json()
    assert body["skills"]["cv_extracted"]["approved"] == 1
    assert body["taxonomy_links"]["cv"] == {"approved_skills": 1, "approved_link": 0, "pending_link": 0, "no_link": 1}
    assert body["retrieval_index"]["profiles"] == {"eligible": 1, "indexed": 0}


@pytest.mark.parametrize("role", ["candidate", "researcher"])
def test_admin_overview_is_admin_only(client: TestClient, db_session: Session, role: str) -> None:
    response = client.get("/admin/overview", headers=headers_for(client, db_session, role, "denied"))
    assert response.status_code == 403
    assert client.get("/admin/overview").status_code in {401, 403}


def test_admin_overview_does_not_write(client: TestClient, db_session: Session) -> None:
    from app.db.models import CandidateProfile, ProcessingLog

    admin = headers_for(client, db_session, "admin", "readonly")
    before = [db_session.scalar(select(func.count()).select_from(model))
              for model in (CandidateProfile, ProcessingLog)]
    assert client.get("/admin/overview", headers=admin).status_code == 200
    db_session.expire_all()
    after = [db_session.scalar(select(func.count()).select_from(model))
             for model in (CandidateProfile, ProcessingLog)]
    assert before == after


def test_overview_splits_job_skills_into_manual_evaluation_and_live(db_session):
    from app.db.models import Job, JobSkill
    from app.services.processing_log_service import SystemOverviewService

    plan = {"manual": ["approved", "pending"], "evaluation": ["approved", "rejected"],
            "arbeitnow": ["pending", "pending"], "greenhouse": ["pending", "approved"]}
    for source, statuses in plan.items():
        job = Job(title=source, description="x", cleaned_description="x", status="processed", source=source,
                  external_id=None if source in {"manual", "evaluation"} else f"{source}-1")
        db_session.add(job)
        db_session.flush()
        for n, status in enumerate(statuses):
            db_session.add(JobSkill(job_id=job.id, raw_text=f"s{n}", normalized_text=f"s{n}", review_status=status))
    db_session.commit()
    skills = SystemOverviewService(db_session).overview()["skills"]
    assert skills["job_by_source"] == {
        "manual": {"approved": 1, "pending": 1, "rejected": 0, "total": 2},
        "evaluation": {"approved": 1, "pending": 0, "rejected": 1, "total": 2},
        "live": {"approved": 1, "pending": 3, "rejected": 0, "total": 4},
    }
    assert skills["job_extracted"]["total"] == 8

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
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
                "raw_text": "Python", "normalized_text": "python", "skill_type": "skill",
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

    if role == "candidate":
        for read_path in ("/jobs", f"/jobs/{job_id}", f"/jobs/{job_id}/sections", f"/jobs/{job_id}/extracted-skills"):
            assert client.get(read_path, headers=headers).status_code == 200
    if role in {"admin", "researcher"}:
        assert {item["name"] for item in client.get("/auth/me", headers=headers).json()["roles"]} == {"candidate", role}

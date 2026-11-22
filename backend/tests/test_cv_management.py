"""CV management: what feeds the matching profile, and CV deletion."""
from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={
        "email": email, "full_name": "Synthetic User", "password": "correct-horse-password"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def paste_cv(client: TestClient, headers: dict[str, str], text: str, name: str) -> str:
    response = client.post("/cvs/paste", headers=headers, json={
        "text": text, "original_filename": name, "consent_to_process": True})
    assert response.status_code == 201
    return response.json()["id"]


def save(client, headers, cv_id, skills):
    response = client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": skills})
    assert response.status_code == 200
    return response.json()


def test_matching_profile_lists_cvs_and_manual_skills(client):
    headers = register(client, "profile@example.com")
    empty = client.get("/candidates/me/matching-profile", headers=headers).json()
    assert empty["cvs"] == [] and empty["retrieval_status"] == "profile_not_ready"

    first = paste_cv(client, headers, "Skills\nPython\nFastAPI", "first.txt")
    second = paste_cv(client, headers, "Skills\nDocker", "second.txt")
    skills = client.get(f"/cvs/{first}/extracted-skills", headers=headers).json()
    skills[0]["review_status"] = "approved"
    skills[1]["review_status"] = "rejected"
    skills.append({"raw_text": "Kubernetes", "normalized_text": "kubernetes", "skill_type": "tool",
                   "evidence_sentence": "", "review_status": "approved"})
    save(client, headers, first, skills)

    body = client.get("/candidates/me/matching-profile", headers=headers).json()
    by_name = {cv["original_filename"]: cv["skills"] for cv in body["cvs"]}
    assert by_name["first.txt"] == {"approved": 1, "pending": 0, "rejected": 1}
    assert by_name["second.txt"] == {"approved": 0, "pending": 1, "rejected": 0}
    assert body["manual_skills"] == {"approved": 1, "pending": 0, "rejected": 0}
    assert body["unattributed_skills"] == {"approved": 0, "pending": 0, "rejected": 0}
    # Approved skills exist, but this test runs without embeddings.
    assert body["retrieval_status"] == "profile_not_indexed" and body["retrieval_message"]

    # Deleting a CV removes its extracted skills; manual skills and the other CV stay.
    assert client.delete(f"/cvs/{first}", headers=headers).status_code == 204
    after = client.get("/candidates/me/matching-profile", headers=headers).json()
    assert [cv["original_filename"] for cv in after["cvs"]] == ["second.txt"]
    assert after["manual_skills"]["approved"] == 1
    remaining = client.get(f"/cvs/{second}/extracted-skills", headers=headers).json()
    assert {skill["normalized_text"] for skill in remaining} == {"docker", "kubernetes"}


def test_matching_profile_and_cv_deletion_are_owner_only(client):
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    cv_id = paste_cv(client, owner, "Skills\nPython", "owner.txt")

    assert client.get("/candidates/me/matching-profile", headers=other).json()["cvs"] == []
    assert client.delete(f"/cvs/{cv_id}", headers=other).status_code == 404
    assert [cv["id"] for cv in client.get("/cvs", headers=owner).json()] == [cv_id]
    assert client.get("/candidates/me/matching-profile").status_code == 401

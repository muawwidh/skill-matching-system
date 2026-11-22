"""Skills added by hand: dedicated add/remove endpoints; a CV skill review never removes them."""
from uuid import UUID

from sqlalchemy import select

from app.db.models import CandidateSkill
from tests.test_recommendations import manager, register

URL = "/candidates/me/manual-skills"


def _cv(client, headers, text="Skills\nPython, SQL"):
    assert client.post("/cvs/paste", headers=headers, json={
        "text": text, "original_filename": "cv.txt", "consent_to_process": True}).status_code == 201
    return client.get("/cvs", headers=headers).json()[0]["id"]


def test_add_list_and_remove_manual_skills(client):
    headers = register(client, "candidate@example.com")
    created = client.post(URL, headers=headers, json={"label": "  Kubernetes   operators "})
    assert created.status_code == 201
    skill = created.json()
    assert (skill["raw_text"], skill["normalized_text"], skill["review_status"], skill["source"]) == (
        "Kubernetes operators", "kubernetes operators", "approved", "manual_review")
    assert client.post(URL, headers=headers, json={"label": "kubernetes OPERATORS"}).status_code == 409
    assert client.post(URL, headers=headers, json={"label": "   "}).status_code == 422
    assert [s["id"] for s in client.get(URL, headers=headers).json()] == [skill["id"]]
    profile = client.get("/candidates/me/matching-profile", headers=headers).json()
    assert profile["manual_skills"]["approved"] == 1  # works without any CV

    assert client.delete(f"{URL}/{skill['id']}", headers=headers).status_code == 204
    assert client.get(URL, headers=headers).json() == []
    assert client.delete(f"{URL}/{skill['id']}", headers=headers).status_code == 404


def test_cv_skill_review_never_removes_manual_skills(client):
    headers = register(client, "candidate@example.com")
    cv_id = _cv(client, headers)
    manual = client.post(URL, headers=headers, json={"label": "Kafka"}).json()
    extracted = [s for s in client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
                 if s["source"] != "manual_review"]
    # Review only the CV's own skills, leaving the hand-added one out of the request.
    for item in extracted:
        item["review_status"] = "approved"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": extracted}).status_code == 200
    assert [s["id"] for s in client.get(URL, headers=headers).json()] == [manual["id"]]
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": []}).status_code == 200
    assert [s["id"] for s in client.get(URL, headers=headers).json()] == [manual["id"]]


def test_cv_skills_and_other_candidates_skills_cannot_be_removed_here(client, db_session):
    headers = register(client, "candidate@example.com")
    other = register(client, "other@example.com")
    cv_id = _cv(client, headers)
    cv_skill = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()[0]
    assert client.delete(f"{URL}/{cv_skill['id']}", headers=headers).status_code == 404
    manual = client.post(URL, headers=headers, json={"label": "Kafka"}).json()
    assert client.delete(f"{URL}/{manual['id']}", headers=other).status_code == 404
    assert db_session.scalar(select(CandidateSkill).where(CandidateSkill.id == UUID(manual["id"]))) is not None


def test_staff_cannot_use_manual_skills(client, db_session):
    staff = manager(client, db_session)
    assert client.post(URL, headers=staff, json={"label": "Kafka"}).status_code == 403
    assert client.delete(f"{URL}/00000000-0000-0000-0000-000000000001", headers=staff).status_code == 403

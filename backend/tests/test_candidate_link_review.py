"""Candidates review taxonomy link suggestions on their own CV skills."""
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ApprovedTaxonomyLink, Role, TaxonomyLinkCandidate, User
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.services.taxonomy_service import TaxonomyService


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={
        "email": email, "full_name": "Synthetic", "password": "correct-horse-password"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def setup_cv(client, db_session, email="owner@example.com"):
    TaxonomyService(db_session).import_bundled_sample()
    headers = register(client, email)
    cv = client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython\nREST APIs", "original_filename": "cv.txt", "consent_to_process": True})
    assert cv.status_code == 201
    return headers, cv.json()["id"]


def groups_by_text(client, headers, cv_id):
    response = client.get(f"/cvs/{cv_id}/taxonomy-links", headers=headers)
    assert response.status_code == 200
    return {group["raw_text"].lower(): group for group in response.json()}


def test_candidate_approves_and_rejects_suggestions_on_own_skills(client, db_session):
    headers, cv_id = setup_cv(client, db_session)
    groups = groups_by_text(client, headers, cv_id)
    rest = groups["rest apis"]
    assert rest["selection"] is None and len(rest["candidates"]) >= 2  # fuzzy: never auto-approved
    first, second = rest["candidates"][0], rest["candidates"][1]

    approved = client.put(f"/cvs/{cv_id}/taxonomy-links/{first['id']}", headers=headers, json={"status": "approved"})
    assert approved.status_code == 200 and approved.json()["review_status"] == "approved"
    owner = db_session.scalar(select(User).where(User.email == "owner@example.com"))
    db_session.expire_all()
    link = db_session.scalar(select(ApprovedTaxonomyLink).where(
        ApprovedTaxonomyLink.extracted_term_id == UUID(rest["extracted_term_id"])))
    assert link.approval_source == "candidate_review" and link.approved_by == owner.id
    event = db_session.scalar(select(TaxonomyReviewEvent).where(
        TaxonomyReviewEvent.extracted_term_id == UUID(rest["extracted_term_id"])))
    assert event.reviewer_id == owner.id and event.action == "approved"

    # Switching to another suggestion needs explicit confirmation against the current selection.
    unconfirmed = client.put(f"/cvs/{cv_id}/taxonomy-links/{second['id']}", headers=headers, json={"status": "approved"})
    assert unconfirmed.status_code == 409
    token = groups_by_text(client, headers, cv_id)["rest apis"]["selection"]["token"]
    replaced = client.put(f"/cvs/{cv_id}/taxonomy-links/{second['id']}", headers=headers, json={
        "status": "approved", "replace_selection": True, "expected_selection_token": token})
    assert replaced.status_code == 200
    assert groups_by_text(client, headers, cv_id)["rest apis"]["selection"]["candidate_id"] == second["id"]

    # Rejecting the selected suggestion removes the link.
    rejected = client.put(f"/cvs/{cv_id}/taxonomy-links/{second['id']}", headers=headers, json={"status": "rejected"})
    assert rejected.status_code == 200
    assert groups_by_text(client, headers, cv_id)["rest apis"]["selection"] is None


def test_candidate_review_is_owner_only_and_staff_review_is_unchanged(client, db_session):
    headers, cv_id = setup_cv(client, db_session)
    other = register(client, "other@example.com")
    other_cv = client.post("/cvs/paste", headers=other, json={
        "text": "Skills\nSQL", "original_filename": "other.txt", "consent_to_process": True}).json()["id"]
    suggestion = groups_by_text(client, headers, cv_id)["rest apis"]["candidates"][0]

    assert client.get(f"/cvs/{cv_id}/taxonomy-links", headers=other).status_code == 404
    # Another user's suggestion through one's own CV, or through the owner's CV, is not found.
    assert client.put(f"/cvs/{other_cv}/taxonomy-links/{suggestion['id']}", headers=other,
                      json={"status": "approved"}).status_code == 404
    assert client.put(f"/cvs/{cv_id}/taxonomy-links/{suggestion['id']}", headers=other,
                      json={"status": "approved"}).status_code == 404
    # Concept correction is not part of the candidate request.
    assert client.put(f"/cvs/{cv_id}/taxonomy-links/{suggestion['id']}", headers=headers,
                      json={"status": "maybe"}).status_code == 422
    # Candidates still cannot use the staff review endpoints.
    assert client.put(f"/taxonomy/link/{suggestion['id']}/approve", headers=headers,
                      json={"status": "approved"}).status_code == 403
    assert client.get("/taxonomy/reviews", headers=headers).status_code == 403

    # Staff review of the same suggestion keeps working, attributed as human review.
    staff_headers = register(client, "staff@example.com")
    staff = db_session.scalar(select(User).where(User.email == "staff@example.com"))
    staff.roles.append(Role(name="researcher", description=""))
    db_session.commit()
    staff_review = client.put(f"/taxonomy/link/{suggestion['id']}/approve", headers=staff_headers,
                              json={"status": "approved"})
    assert staff_review.status_code == 200
    db_session.expire_all()
    link = db_session.scalar(select(ApprovedTaxonomyLink).where(
        ApprovedTaxonomyLink.link_candidate_id == UUID(suggestion["id"])))
    assert link.approval_source == "human_review" and link.approved_by == staff.id


def test_job_suggestions_cannot_be_reviewed_through_the_cv_route(client, db_session):
    headers, cv_id = setup_cv(client, db_session)
    staff_headers = register(client, "manager@example.com")
    staff = db_session.scalar(select(User).where(User.email == "manager@example.com"))
    staff.roles.append(Role(name="admin", description=""))
    db_session.commit()
    job = client.post("/jobs", headers=staff_headers, json={
        "title": "Job", "company": "", "location": "", "employment_type": "",
        "description": "Required skills\nREST APIs"}).json()
    job_suggestion = db_session.scalar(select(TaxonomyLinkCandidate).where(
        TaxonomyLinkCandidate.term_source == "job"))
    assert job_suggestion is not None and job["id"]
    assert client.put(f"/cvs/{cv_id}/taxonomy-links/{job_suggestion.id}", headers=headers,
                      json={"status": "approved"}).status_code == 404

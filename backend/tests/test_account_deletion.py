"""Candidate account deletion (D047)."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (ApprovedTaxonomyLink, CandidateProfile, CandidateProfileEmbedding,
                           CandidateSkill, CvDocument, CvSection, ExtractedCandidateTerm, ProcessingLog,
                           RefreshToken, Role, TaxonomyLinkCandidate, User)
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.representation import DIMENSION
from app.services.retrieval_service import RetrievalService
from app.services.taxonomy_service import TaxonomyService
from tests.conftest import DeterministicTestTokenizer

PASSWORD = "correct-horse-password"


class FakeEmbedder:
    tokenizer = DeterministicTestTokenizer()

    def encode(self, text):
        return [1.0] + [0.0] * (DIMENSION - 1)


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "full_name": "Synthetic", "password": PASSWORD})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def count(db: Session, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def populate(client: TestClient, db: Session, email: str) -> dict[str, str]:
    """A candidate with two CVs, reviewed and manual skills, a taxonomy link and review and an embedding."""
    headers = register(client, email)
    for text in ("Skills\nPython\nFastAPI", "Skills\nSQL"):
        cv = client.post("/cvs/paste", headers=headers, json={
            "text": text, "original_filename": "cv.txt", "consent_to_process": True}).json()
        skills = client.get(f"/cvs/{cv['id']}/extracted-skills", headers=headers).json()
        for skill in skills:
            skill["review_status"] = "approved"
        skills.append({"raw_text": "Teaching", "normalized_text": "teaching", "skill_type": "skill",
                       "evidence_sentence": "", "review_status": "approved"})
        assert client.put(f"/cvs/{cv['id']}/extracted-skills", headers=headers, json={"skills": skills}).status_code == 200
    user = db.scalar(select(User).where(User.email == email))
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    RetrievalService(db, None, DeterministicTestTokenizer()).index_profile(profile.id, FakeEmbedder())
    candidate = db.scalar(select(TaxonomyLinkCandidate).where(TaxonomyLinkCandidate.term_source == "candidate"))
    reviewer = register(client, f"staff-{email}")
    staff = db.scalar(select(User).where(User.email == f"staff-{email}"))
    staff.roles.append(db.scalar(select(Role).where(Role.name == "admin")) or Role(name="admin", description=""))
    db.commit()
    TaxonomyService(db).review_link(candidate.id, "rejected", None, staff)
    db.commit()
    return headers


def test_account_deletion_removes_all_candidate_data(client, db_session):
    TaxonomyService(db_session).import_bundled_sample()
    headers = populate(client, db_session, "erase@example.com")
    keep = populate(client, db_session, "keep@example.com")
    user = db_session.scalar(select(User).where(User.email == "erase@example.com"))
    profile = db_session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    documents = list(db_session.scalars(select(CvDocument.id).where(CvDocument.candidate_profile_id == profile.id)))
    terms = list(db_session.scalars(select(ExtractedCandidateTerm.id).where(ExtractedCandidateTerm.cv_document_id.in_(documents))))
    assert count(db_session, CandidateProfileEmbedding, CandidateProfileEmbedding.candidate_profile_id == profile.id) == 1
    assert count(db_session, ApprovedTaxonomyLink, ApprovedTaxonomyLink.extracted_term_id.in_(terms)) > 0
    assert count(db_session, TaxonomyReviewEvent, TaxonomyReviewEvent.extracted_term_id.in_(terms)) == 1
    other_before = {model.__name__: count(db_session, model) for model in (CvDocument, CandidateSkill, TaxonomyReviewEvent)}
    profile_id, user_id = profile.id, user.id

    assert client.post("/auth/delete-account", headers=headers, json={"password": PASSWORD}).status_code == 204
    db_session.expire_all()
    assert db_session.get(User, user_id) is None
    assert db_session.get(CandidateProfile, profile_id) is None
    for model, where in (
        (CvDocument, CvDocument.id.in_(documents)),
        (CvSection, CvSection.cv_document_id.in_(documents)),
        (ExtractedCandidateTerm, ExtractedCandidateTerm.id.in_(terms)),
        (CandidateSkill, CandidateSkill.candidate_profile_id == profile_id),
        (TaxonomyLinkCandidate, TaxonomyLinkCandidate.extracted_term_id.in_(terms)),
        (ApprovedTaxonomyLink, ApprovedTaxonomyLink.extracted_term_id.in_(terms)),
        (TaxonomyReviewEvent, TaxonomyReviewEvent.extracted_term_id.in_(terms)),
        (CandidateProfileEmbedding, CandidateProfileEmbedding.candidate_profile_id == profile_id),
        (ProcessingLog, ProcessingLog.entity_id.in_([profile_id, *documents])),
        (RefreshToken, RefreshToken.user_id == user_id),
    ):
        assert count(db_session, model, where) == 0, model.__name__
    # The other candidate is untouched, and the old token no longer works.
    assert count(db_session, CvDocument) == other_before["CvDocument"] - len(documents)
    assert client.get("/cvs", headers=keep).status_code == 200 and len(client.get("/cvs", headers=keep).json()) == 2
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": "erase@example.com", "password": PASSWORD}).status_code == 401


def test_wrong_password_or_staff_account_is_refused(client, db_session):
    headers = register(client, "careful@example.com")
    response = client.post("/auth/delete-account", headers=headers, json={"password": "wrong-password"})
    assert response.status_code == 403
    assert client.get("/auth/me", headers=headers).status_code == 200

    staff_headers = register(client, "admin@example.com")
    staff = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    staff.roles.append(Role(name="admin", description=""))
    db_session.commit()
    assert client.post("/auth/delete-account", headers=staff_headers, json={"password": PASSWORD}).status_code == 403
    assert client.post("/auth/delete-account", json={"password": PASSWORD}).status_code == 401

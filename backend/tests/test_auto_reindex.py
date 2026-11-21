"""Automatic re-embedding after committed changes (D046)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CandidateProfile, CandidateProfileEmbedding, JobEmbedding, Role, User
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval import auto_reindex
from app.retrieval.representation import DIMENSION
from app.services.retrieval_service import RetrievalService
from tests.conftest import DeterministicTestTokenizer


class FakeEmbedder:
    tokenizer = DeterministicTestTokenizer()

    def __init__(self):
        self.calls = 0

    def encode(self, text):
        self.calls += 1
        vector = [0.0] * DIMENSION
        vector[0] = 1.0
        vector[1] = (len(text) % 97) / 97
        return vector


@pytest.fixture()
def embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr(settings, "AUTO_REINDEX", True)
    monkeypatch.setattr(auto_reindex, "get_embedder", lambda: fake)
    return fake


def register(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    response = client.post("/auth/register", json={
        "email": email, "full_name": "Synthetic User", "password": "correct-horse-password"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def paste_cv(client: TestClient, headers: dict[str, str], text: str = "Skills\nPython\nFastAPI") -> str:
    response = client.post("/cvs/paste", headers=headers, json={
        "text": text, "original_filename": "cv.txt", "consent_to_process": True})
    assert response.status_code == 201
    return response.json()["id"]


def review_all(client: TestClient, headers: dict[str, str], cv_id: str, status: str) -> None:
    skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = status
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": skills}).status_code == 200


def readiness(db_session: Session, email: str) -> str:
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == email))
    return RetrievalService(db_session).profile_readiness(user)[0]


def profile_vector(db_session: Session, email: str):
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == email))
    profile = db_session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    return db_session.scalar(select(CandidateProfileEmbedding).where(
        CandidateProfileEmbedding.candidate_profile_id == profile.id))


def test_skill_review_reembeds_the_profile(client, db_session, embedder):
    headers, email = register(client, "auto@example.com")
    cv_id = paste_cv(client, headers)
    assert readiness(db_session, email) == "no_approved_skills"  # nothing approved yet, nothing embedded

    review_all(client, headers, cv_id, "approved")
    assert readiness(db_session, email) == "ready"
    first_hash = profile_vector(db_session, email).source_hash

    # A further review changes the profile input; the vector follows without the CLI.
    skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
    skills[0]["review_status"] = "rejected"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": skills}).status_code == 200
    assert readiness(db_session, email) == "ready"
    assert profile_vector(db_session, email).source_hash != first_hash


def test_cv_deletion_reembeds_from_the_remaining_cv(client, db_session, embedder):
    headers, email = register(client, "delete@example.com")
    first = paste_cv(client, headers, "Skills\nPython")
    second = paste_cv(client, headers, "Skills\nDocker")
    review_all(client, headers, first, "approved")
    review_all(client, headers, second, "approved")
    before = profile_vector(db_session, email).source_hash

    assert client.delete(f"/cvs/{second}", headers=headers).status_code == 204
    assert readiness(db_session, email) == "ready"
    assert profile_vector(db_session, email).source_hash != before

    # Deleting the last CV leaves no approved skill: the stale vector is not used.
    assert client.delete(f"/cvs/{first}", headers=headers).status_code == 204
    assert readiness(db_session, email) == "no_approved_skills"


def test_job_creation_and_review_reembed_the_job(client, db_session, embedder):
    headers, email = register(client, "staff@example.com")
    user = db_session.scalar(select(User).where(User.email == email))
    user.roles.append(Role(name="admin", description="Job management"))
    db_session.commit()
    job = client.post("/jobs", headers=headers, json={
        "title": "Engineer", "company": "Acme", "location": "", "employment_type": "",
        "description": "Required skills\nPython\nDocker"}).json()
    assert job["id"] in {str(job_id) for job_id in RetrievalService(db_session).fresh_job_ids()}
    before = db_session.scalar(select(JobEmbedding)).source_hash

    skill = client.get(f"/jobs/{job['id']}/extracted-skills", headers=headers).json()[0]
    skill["review_status"] = "rejected"
    assert client.put(f"/jobs/{job['id']}/extracted-skills/{skill['id']}", headers=headers, json=skill).status_code == 200
    db_session.expire_all()
    vector = db_session.scalar(select(JobEmbedding))
    assert vector.status == "ready" and vector.source_hash != before

    assert client.post(f"/jobs/{job['id']}/archive", headers=headers).status_code == 200
    db_session.expire_all()
    assert db_session.scalar(select(JobEmbedding)).status == "stale"  # archived jobs are not retrievable


def test_taxonomy_link_change_reembeds_through_term_invalidation(client, db_session, embedder):
    headers, email = register(client, "link@example.com")
    cv_id = paste_cv(client, headers)
    review_all(client, headers, cv_id, "approved")
    vector = profile_vector(db_session, email)
    vector.status = "stale"
    db_session.commit()  # a direct status change is not an invalidation: nothing is recorded
    assert readiness(db_session, email) == "profile_not_indexed"

    from app.db.models import ExtractedCandidateTerm
    term = db_session.scalar(select(ExtractedCandidateTerm))
    RetrievalRepository(db_session).invalidate_term("candidate", term.id)  # what a link review does
    db_session.commit()
    assert readiness(db_session, email) == "ready"


def test_rollback_and_release_wide_invalidation_do_not_reembed(client, db_session, embedder):
    headers, email = register(client, "rollback@example.com")
    cv_id = paste_cv(client, headers)
    review_all(client, headers, cv_id, "approved")
    profile_id = profile_vector(db_session, email).candidate_profile_id
    calls = embedder.calls

    RetrievalRepository(db_session).invalidate_profile(profile_id)
    db_session.rollback()
    RetrievalRepository(db_session).invalidate_all()  # taxonomy import: bulk CLI, not automatic
    db_session.commit()
    assert embedder.calls == calls
    assert readiness(db_session, email) == "profile_not_indexed"


def test_missing_model_leaves_vectors_stale_without_failing_the_request(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_REINDEX", True)

    def unavailable():
        raise RuntimeError("Pinned E5 model is unavailable locally.")

    monkeypatch.setattr(auto_reindex, "get_embedder", unavailable)
    headers, email = register(client, "nomodel@example.com")
    cv_id = paste_cv(client, headers)
    review_all(client, headers, cv_id, "approved")  # request still succeeds
    assert readiness(db_session, email) == "profile_not_indexed"


def test_disabled_setting_keeps_the_cli_only_behaviour(client, db_session, monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr(auto_reindex, "get_embedder", lambda: fake)
    assert settings.AUTO_REINDEX is False  # test default (conftest)
    headers, email = register(client, "off@example.com")
    review_all(client, headers, paste_cv(client, headers), "approved")
    assert fake.calls == 0
    assert readiness(db_session, email) == "profile_not_indexed"


def test_ready_job_ids_follow_stored_status_without_rebuilding_inputs(client, db_session, embedder, monkeypatch):
    """The Jobs page unindexed count reads stored status only (2026-11-21 latency fix)."""
    headers, email = register(client, "staff2@example.com")
    user = db_session.scalar(select(User).where(User.email == email))
    user.roles.append(Role(name="admin", description="Job management"))
    db_session.commit()
    ids = [client.post("/jobs", headers=headers, json={
        "title": f"Engineer {n}", "company": "Acme", "location": "", "employment_type": "",
        "description": "Required skills\nPython"}).json()["id"] for n in range(2)]
    service = RetrievalService(db_session)
    expected = set(service.fresh_job_ids())
    assert {str(i) for i in expected} == set(ids)

    def must_not_rebuild(*args, **kwargs):
        raise AssertionError("representation rebuilt")
    monkeypatch.setattr(RetrievalRepository, "job_input", must_not_rebuild)
    assert service.ready_job_ids() == expected
    assert service.ready_job_ids(exclude_sources={"manual"}) == set()
    # A stale vector (job changed, not yet re-embedded) is not ready.
    stale = next(iter(expected))
    db_session.query(JobEmbedding).filter(JobEmbedding.job_id == stale).update({"status": "stale"})
    assert service.ready_job_ids() == expected - {stale}

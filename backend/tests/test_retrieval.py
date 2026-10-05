from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.auth import get_current_user
from app.db.models import (CandidateJobMatch, CandidateProfileEmbedding, CandidateSkill, Job,
                           JobEmbedding, JobSkill, Role, User, ExtractedCandidateTerm)
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import DocumentRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.evaluation import retrieval_metrics
from app.retrieval.embedder import LocalE5Embedder
from app.retrieval.representation import (DIMENSION, MODEL_ID, MODEL_REVISION, TEMPLATE_VERSION,
                                          bounded_text, candidate_representation, job_representation)
from app.services.retrieval_service import RetrievalService
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.taxonomy_service import TaxonomyService
from app.services.job_service import JobService


class FakeEmbedder:
    def __init__(self):
        self.texts = []

    def encode(self, text):
        self.texts.append(text)
        vector = [0.0] * DIMENSION
        vector[0] = 1.0 if "Python" in text else 0.5
        vector[1] = 1.0
        return vector


class WordTokenizer:
    def encode(self, text, **_):
        return [0] + list(range(2, 2 + len(text.split()))) + [1]

    def decode(self, tokens, **_):
        return " ".join("x" for _ in tokens)

    def num_special_tokens_to_add(self, **_):
        return 2


def seed(db):
    user = User(email=f"retrieval-{uuid4()}@example.org", full_name="Candidate", hashed_password="unused")
    user.roles.append(db.scalar(select(Role).where(Role.name == "candidate")) or Role(name="candidate", description=""))
    db.add(user)
    db.flush()
    profile = DocumentRepository(db).get_or_create_candidate_profile(user.id)
    profile.consent_to_process_cv = True
    skill = CandidateSkill(candidate_profile_id=profile.id, raw_text="Python", normalized_text="python",
                           evidence_sentence="Built an API", review_status="approved", source="manual_review")
    pending = CandidateSkill(candidate_profile_id=profile.id, raw_text="Rust", normalized_text="rust",
                             evidence_sentence="Pending", review_status="pending", source="manual_review")
    rejected = CandidateSkill(candidate_profile_id=profile.id, raw_text="Go", normalized_text="go",
                              evidence_sentence="Rejected", review_status="rejected", source="manual_review")
    job = Job(title="Python Engineer", company="Example", location="Vilnius", description="Build APIs",
              cleaned_description="Build APIs", status="processed")
    db.add_all([skill, pending, rejected, job])
    db.flush()
    db.add(JobSkill(job_id=job.id, raw_text="Python", normalized_text="python", requirement_type="required",
                    review_status="pending", source="manual_review"))
    db.commit()
    return user, profile, skill, pending, rejected, job


def test_representation_filters_orders_hashes_and_prefixes():
    rows = [dict(id="2", text="Python", status="pending", evidence="unconfirmed"),
            dict(id="1", text="Python", status="approved", evidence="Built API", canonical="Python programming", release="v1"),
            dict(id="3", text="Go", status="rejected", evidence="incorrect")]
    value = candidate_representation(rows)
    assert value.text.startswith("query: Skills: Python; Python programming")
    assert "Built API" in value.text and "unconfirmed" not in value.text and "Go" not in value.text
    assert value == candidate_representation(list(reversed(rows)))
    changed = [dict(item) for item in rows]
    changed[0]["evidence"] = "different pending evidence"
    assert candidate_representation(changed).source_hash != value.source_hash
    assert candidate_representation([rows[0], rows[2]]) is None
    job = dict(title="Engineer", location="Vilnius", employment_type="full-time", description="Description")
    terms = [dict(id="2", text="Go", status="rejected", requirement="required"),
             dict(id="1", text="Python", status="pending", requirement="required", canonical="Python programming", release="v1"),
             dict(id="3", text="SQL", status="approved", requirement="preferred")]
    result = job_representation(job, terms)
    assert result.text.startswith("passage: Job title: Engineer")
    assert "Required skills: Python; Python programming" in result.text
    assert "Preferred skills: SQL" in result.text and "Go" not in result.text
    assert result == job_representation(job, list(reversed(terms)))
    assert job_representation({**job, "description": "Changed"}, terms).source_hash != result.source_hash


def test_token_budget_keeps_high_priority_prefix():
    tokenizer = WordTokenizer()
    original = "query: Skills: Python " + " ".join(f"word{i}" for i in range(600))
    bounded = bounded_text(original, tokenizer)
    assert len(tokenizer.encode(bounded)) <= 512
    assert len(bounded.split()) == 510
    assert bounded_text("passage: Short", tokenizer) == "passage: Short"


def test_index_idempotent_invalidation_failure_retry_and_score_isolation(db_session):
    db = db_session
    user, profile, skill, pending, rejected, job = seed(db)
    fake = FakeEmbedder()
    service = RetrievalService(db)
    assert service.index_profile(profile.id, fake).outcome == "indexed"
    assert service.index_job(job.id, fake).outcome == "indexed"
    db.commit()
    assert len(fake.texts) == 2
    assert "Rust" not in fake.texts[0] and "Go" not in fake.texts[0]
    assert service.index_profile(profile.id, fake).outcome == "unchanged"
    assert service.index_job(job.id, fake).outcome == "unchanged"
    assert len(fake.texts) == 2
    assert not db.scalars(select(CandidateJobMatch)).all()

    DocumentRepository(db).update_candidate_skill(skill, "Python", "python", "skill", "Changed evidence", "approved")
    assert db.scalar(select(CandidateProfileEmbedding)).status == "stale"
    db.commit()
    class FailedEmbedder:
        def encode(self, text):
            raise RuntimeError("inference failed")
    with pytest.raises(RuntimeError):
        service.index_profile(profile.id, FailedEmbedder())
    db.rollback()
    assert db.scalar(select(CandidateProfileEmbedding)).status == "stale"
    assert service.index_profile(profile.id, fake).outcome == "indexed"
    db.commit()
    assert db.scalar(select(CandidateProfileEmbedding)).status == "ready"
    job_skill = db.scalar(select(JobSkill).where(JobSkill.job_id == job.id))
    DocumentRepository(db).update_job_skill(job_skill, "Python", "python", "skill", "required", "evidence", "rejected")
    assert db.scalar(select(JobEmbedding)).status == "stale"
    db.commit()
    assert service.index_job(job.id, fake).outcome == "indexed"
    assert "Required skills" not in fake.texts[-1]
    assert not db.scalars(select(CandidateJobMatch)).all()


def test_retrieval_auth_readiness_and_ownership(db_session):
    user, profile, skill, pending, rejected, job = seed(db_session)
    other, _, _, _, _, _ = seed(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        assert client.get("/retrieval/jobs").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert client.get("/retrieval/jobs").status_code == 409
        app.dependency_overrides[get_current_user] = lambda: other
        assert client.get("/retrieval/jobs").status_code == 409
        admin = User(email=f"admin-{uuid4()}@example.org", full_name="Admin", hashed_password="unused")
        admin.roles.append(Role(name="admin", description=""))
        db_session.add(admin)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: admin
        assert client.get("/retrieval/jobs").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user
        assert client.get("/retrieval/jobs?limit=101").status_code == 422


def test_synthetic_metrics_calculation_only():
    measured = retrieval_metrics([{"relevant_job_ids": ["a", "b"], "retrieved_job_ids": ["c", "a", "b"]}])
    assert measured["recall_at_5"] == measured["recall_at_10"] == measured["recall_at_20"] == 1
    assert measured["mrr"] == .5
    with pytest.raises(ValueError):
        retrieval_metrics([])


def test_missing_local_model_fails_without_download(tmp_path):
    with pytest.raises(RuntimeError, match="unavailable locally"):
        LocalE5Embedder(str(tmp_path / "missing"))


def test_taxonomy_selection_and_extraction_review_invalidate_without_changing_audit(db_session):
    db = db_session
    user, profile, skill, pending, rejected, job = seed(db)
    term = ExtractedCandidateTerm(cv_document_id=DocumentRepository(db).create_cv_document(
        profile.id, "example.txt", "text/plain", "paste", "", "", 0).id,
        raw_text="Python", normalized_text="python", term_type="skill", extraction_method="test")
    db.add(term)
    db.flush()
    skill.extracted_term_id = term.id
    taxonomy = TaxonomyRepository(db)
    source = taxonomy.get_or_create_source("TEST", "Test", "", "")
    version = taxonomy.replace_version(source, "test", "", "test", "", True)
    first = taxonomy.add_concept(version.id, "a", "Python programming", "python programming", "", "skill", "en", [], {})
    second = taxonomy.add_concept(version.id, "b", "Python development", "python development", "", "skill", "en", [], {})
    a = taxonomy.add_link_candidate("candidate", term.id, "Python", "python", first.id, "fuzzy", .8, 1, "pending")
    b = taxonomy.add_link_candidate("candidate", term.id, "Python", "python", second.id, "fuzzy", .7, 2, "pending")
    taxonomy.approve_candidate(a, "human_review", user.id)
    db.commit()
    fake = FakeEmbedder()
    retrieval = RetrievalService(db)
    assert retrieval.index_profile(profile.id, fake).outcome == "indexed"
    db.commit()
    before = retrieval.repository.profile_embedding(profile.id).source_hash
    assert "Python programming" in fake.texts[-1]
    token = TaxonomyService._selection_token(taxonomy.selected_link("candidate", term.id))
    TaxonomyService(db).review_link(b.id, "approved", None, user, True, token)
    assert retrieval.repository.profile_embedding(profile.id).status == "stale"
    assert retrieval.index_profile(profile.id, fake).outcome == "indexed"
    assert "Python development" in fake.texts[-1] and "Python programming" not in fake.texts[-1]
    assert retrieval.repository.profile_embedding(profile.id).source_hash != before
    assert len(taxonomy.review_history("candidate", term.id, 20, 0)) == 1
    db.commit()
    TaxonomyService(db).review_link(b.id, "rejected", None, user)
    assert retrieval.repository.profile_embedding(profile.id).status == "stale"
    assert len(taxonomy.review_history("candidate", term.id, 20, 0)) == 2


def test_job_archive_and_all_rejected_profile_are_not_ready(db_session):
    db = db_session
    user, profile, skill, pending, rejected, job = seed(db)
    fake = FakeEmbedder()
    retrieval = RetrievalService(db)
    retrieval.index_profile(profile.id, fake)
    retrieval.index_job(job.id, fake)
    db.commit()
    JobService(db).archive_job(job.id)
    assert db.scalar(select(JobEmbedding)).status == "stale"
    assert retrieval.index_job(job.id, fake).outcome == "not_ready"
    DocumentRepository(db).update_candidate_skill(skill, "Python", "python", "skill", "", "rejected")
    assert retrieval.index_profile(profile.id, fake).outcome == "not_ready"
    db.commit()
    assert db.scalar(select(CandidateProfileEmbedding)).status == "stale"

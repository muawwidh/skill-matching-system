"""CV lifecycle checks use disposable schemas in the isolated verification database."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import (
    ApprovedTaxonomyLink, CandidateJobMatch, CandidateProfileEmbedding, CandidateSkill, CvDocument,
    ExtractedCandidateTerm, Job, JobSkill, TaxonomyConcept, TaxonomyLinkCandidate, TaxonomyVersion, User,
)
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import DocumentRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.schemas.documents import CandidateSkillReviewRequest, CvPasteRequest
from app.services.cv_service import CvService
from app.services.matching_service import MatchingService
from app.services.retrieval_service import RetrievalService
from app.services.skill_service import SkillService
from app.services.taxonomy_service import TaxonomyService
from test_taxonomy_postgres import pg_database  # noqa: F401


class FakeEmbedder:
    def encode(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 383


def persisted_row(item) -> str:
    columns = {column.key: getattr(item, column.key) for column in inspect(item).mapper.column_attrs}
    return json.dumps(columns, sort_keys=True, default=str)


def persisted_rows(db: Session, model, *criteria) -> list[str]:
    return sorted(persisted_row(item) for item in db.scalars(select(model).where(*criteria)))


def paste(db: Session, user: User, name: str, text: str) -> CvDocument:
    return CvService(db).paste_cv(user, CvPasteRequest(
        text=text, original_filename=name, consent_to_process=True,
    ))


def document_rows(db: Session, cv_id):
    terms = list(db.scalars(select(ExtractedCandidateTerm).where(ExtractedCandidateTerm.cv_document_id == cv_id)))
    ids = [term.id for term in terms]
    skills = list(db.scalars(select(CandidateSkill).where(CandidateSkill.extracted_term_id.in_(ids))))
    return terms, skills


def taxonomy_snapshot(db: Session, cv_id):
    terms, skills = document_rows(db, cv_id)
    ids = [term.id for term in terms]
    candidates = list(db.scalars(select(TaxonomyLinkCandidate).where(
        TaxonomyLinkCandidate.term_source == "candidate", TaxonomyLinkCandidate.extracted_term_id.in_(ids)
    )))
    links = list(db.scalars(select(ApprovedTaxonomyLink).where(
        ApprovedTaxonomyLink.term_source == "candidate", ApprovedTaxonomyLink.extracted_term_id.in_(ids)
    )))
    events = list(db.scalars(select(TaxonomyReviewEvent).where(
        TaxonomyReviewEvent.term_source == "candidate", TaxonomyReviewEvent.extracted_term_id.in_(ids)
    )))
    return {
        "terms": sorted(persisted_row(item) for item in terms),
        "skills": sorted(persisted_row(item) for item in skills),
        "candidates": sorted(persisted_row(item) for item in candidates),
        "links": sorted(persisted_row(item) for item in links),
        "events": sorted(persisted_row(item) for item in events),
    }


def review_alternative(db: Session, user: User, skill: CandidateSkill, *, approve: bool = False):
    concept = db.scalar(select(TaxonomyConcept).where(TaxonomyConcept.preferred_label == "Programming"))
    assert concept is not None
    alternative = TaxonomyRepository(db).add_link_candidate(
        "candidate", skill.extracted_term_id, skill.raw_text, skill.normalized_text,
        concept.id, "fuzzy", .7, 99, "pending",
    )
    db.commit()
    service = TaxonomyService(db)
    service.review_link(alternative.id, "rejected", None, user)
    if approve:
        selected = TaxonomyRepository(db).selected_link("candidate", skill.extracted_term_id)
        service.review_link(
            alternative.id, "approved", None, user, True, service._selection_token(selected)
        )
    return alternative.id


def select_ambiguous_python_for_lifecycle_test(db: Session, user: User, skill: CandidateSkill) -> None:
    repo = TaxonomyRepository(db)
    candidates = repo.term_candidates("candidate", skill.extracted_term_id)
    preferred = [item for item in candidates if item.match_method == "exact_preferred" and item.confidence_score == 1.0]
    assert len(preferred) >= 2
    assert repo.selected_link("candidate", skill.extracted_term_id) is None
    TaxonomyService(db).review_link(preferred[0].id, "approved", None, user)
    assert repo.selected_link("candidate", skill.extracted_term_id).link_candidate_id == preferred[0].id


def test_cv_skill_apis_keep_extraction_scoped_and_manual_profile_wide(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-api-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv1 = paste(db, user, "one.txt", "Skills\nPython")
        cv2 = paste(db, user, "two.txt", "Skills\nPython\nDocker")
        cv1_id, cv2_id = cv1.id, cv2.id
        cv1_ids = {item.id for item in document_rows(db, cv1_id)[1]}
        cv2_ids = {item.id for item in document_rows(db, cv2_id)[1]}
        assert cv1_ids.isdisjoint(cv2_ids)
        manual = DocumentRepository(db).create_candidate_skill(
            cv1.candidate_profile_id, "Go", "go", "skill", "Manual evidence", "approved"
        )
        db.commit()
        manual_id = manual.id
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as client:
            for cv_id, own_ids, other_ids in ((cv1_id, cv1_ids, cv2_ids), (cv2_id, cv2_ids, cv1_ids)):
                skills_response = client.get(f"/cvs/{cv_id}/extracted-skills")
                groups_response = client.get(f"/cvs/{cv_id}/skill-groups")
                assert skills_response.status_code == 200
                assert groups_response.status_code == 200
                expected = {str(item) for item in own_ids | {manual_id}}
                assert {item["id"] for item in skills_response.json()} == expected
                group_ids = {item["id"] for group in groups_response.json() for item in group["occurrences"]}
                assert group_ids == expected
                assert group_ids.isdisjoint({str(item) for item in other_ids})


def test_overlapping_cv_deletion_preserves_other_term_and_taxonomy_rows(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-overlap-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv1 = paste(db, user, "one.txt", "Skills\nPython\nSQL")
        cv2 = paste(db, user, "two.txt", "Skills\nPython\nDocker")
        cv1_id, cv2_id = cv1.id, cv2.id
        old_terms, old_skills = document_rows(db, cv1_id)
        kept_terms, kept_skills = document_rows(db, cv2_id)
        old_python = next(item for item in old_skills if item.normalized_text == "python")
        kept_python = next(item for item in kept_skills if item.normalized_text == "python")
        old_python.review_status = "rejected"
        kept_python.review_status = "approved"
        db.commit()
        select_ambiguous_python_for_lifecycle_test(db, user, old_python)
        select_ambiguous_python_for_lifecycle_test(db, user, kept_python)
        review_alternative(db, user, kept_python)
        assert TaxonomyRepository(db).selected_link("candidate", old_python.extracted_term_id)
        assert TaxonomyRepository(db).selected_link("candidate", kept_python.extracted_term_id)
        kept_snapshot = taxonomy_snapshot(db, cv2_id)
        kept_python_id = kept_python.id
        old_term_ids = [item.id for item in old_terms]
        kept_term_ids = [item.id for item in kept_terms]
        CvService(db).delete_my_cv(user, cv1_id)
    with Session(engine) as fresh:
        assert taxonomy_snapshot(fresh, cv2_id) == kept_snapshot
        assert fresh.get(CandidateSkill, kept_python_id) is not None
        assert all(fresh.get(ExtractedCandidateTerm, item_id) is not None for item_id in kept_term_ids)
        assert not persisted_rows(fresh, CandidateSkill, CandidateSkill.extracted_term_id.in_(old_term_ids))
        assert not persisted_rows(fresh, ExtractedCandidateTerm, ExtractedCandidateTerm.id.in_(old_term_ids))
        assert not persisted_rows(fresh, TaxonomyLinkCandidate,
            TaxonomyLinkCandidate.term_source == "candidate", TaxonomyLinkCandidate.extracted_term_id.in_(old_term_ids))
        assert not persisted_rows(fresh, ApprovedTaxonomyLink,
            ApprovedTaxonomyLink.term_source == "candidate", ApprovedTaxonomyLink.extracted_term_id.in_(old_term_ids))


def test_deleted_cv_audit_snapshots_retain_history_without_cv_evidence(pg_database):
    engine, _, _ = pg_database
    raw_sentinel = "RAW_CV_SENTINEL_8e6f14d2"
    evidence_sentinel = "EVIDENCE_SENTINEL_9b72c4a1"
    with Session(engine) as db:
        user = User(email=f"cv-audit-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv = paste(db, user, "sentinel.txt",
            f"Summary\n{raw_sentinel}\n\nSkills\nPython {evidence_sentinel}")
        cv_id = cv.id
        terms, skills = document_rows(db, cv_id)
        assert evidence_sentinel in next(item for item in terms if item.normalized_text == "python").evidence_sentence
        python = next(item for item in skills if item.normalized_text == "python")
        review_alternative(db, user, python)
        term_ids = [item.id for item in terms]
        before = persisted_rows(db, TaxonomyReviewEvent,
            TaxonomyReviewEvent.term_source == "candidate", TaxonomyReviewEvent.extracted_term_id.in_(term_ids))
        assert before
        CvService(db).delete_my_cv(user, cv_id)
    with Session(engine) as fresh:
        after = persisted_rows(fresh, TaxonomyReviewEvent,
            TaxonomyReviewEvent.term_source == "candidate", TaxonomyReviewEvent.extracted_term_id.in_(term_ids))
        assert after == before
        snapshots = [json.loads(row) for row in after]
        assert all(raw_sentinel not in json.dumps(item["before_state"])
                   and raw_sentinel not in json.dumps(item["after_state"])
                   and evidence_sentinel not in json.dumps(item["before_state"])
                   and evidence_sentinel not in json.dumps(item["after_state"])
                   for item in snapshots)


def test_two_cvs_reprocessing_and_deletion_preserve_other_evidence(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-life-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv1 = paste(db, user, "first.txt", "Skills\nPython\nSQL\nFastAPI")
        cv1_id, user_id, profile_id = cv1.id, user.id, cv1.candidate_profile_id
        terms1, skills1 = document_rows(db, cv1_id)
        python = next(skill for skill in skills1 if skill.normalized_text == "python")
        sql = next(skill for skill in skills1 if skill.normalized_text == "sql")
        fastapi = next(skill for skill in skills1 if skill.normalized_text == "fastapi")
        python.review_status, sql.review_status = "approved", "rejected"
        assert fastapi.review_status == "pending"
        db.commit()
        select_ambiguous_python_for_lifecycle_test(db, user, python)
        assert TaxonomyRepository(db).selected_link("candidate", python.extracted_term_id)
        concept = db.scalar(select(TaxonomyConcept).where(TaxonomyConcept.preferred_label == "Programming"))
        assert concept is not None
        alternative = TaxonomyRepository(db).add_link_candidate(
            "candidate", python.extracted_term_id, "Python", "python", concept.id, "fuzzy", .7, 99, "pending"
        )
        db.commit()
        TaxonomyService(db).review_link(alternative.id, "rejected", None, user)
        assert db.scalar(select(TaxonomyReviewEvent).where(TaxonomyReviewEvent.candidate_id == alternative.id))
        manual = DocumentRepository(db).create_candidate_skill(profile_id, "Go", "go", "skill", "Manual", "approved")
        db.commit()
        manual_id = manual.id
        original = taxonomy_snapshot(db, cv1_id)
        cv1_term_ids = [term.id for term in terms1]

        cv2 = paste(db, user, "second.txt", "Skills\nDocker")
        cv2_id = cv2.id
        terms2, skills2 = document_rows(db, cv2_id)
        docker = next(skill for skill in skills2 if skill.normalized_text == "docker")
        docker.review_status = "approved"
        db.commit()
        docker_id, docker_term_id = docker.id, docker.extracted_term_id
    with Session(engine) as fresh:
        assert taxonomy_snapshot(fresh, cv1_id) == original
        assert {skill.normalized_text for skill in fresh.scalars(select(CandidateSkill).where(
            CandidateSkill.candidate_profile_id == profile_id, CandidateSkill.review_status == "approved"
        ))} >= {"python", "docker", "go"}
        source = RetrievalRepository(fresh).profile_input(profile_id)
        assert source is not None and "Python" in source.text and "Docker" in source.text
        assert "SQL" not in source.text

    with Session(engine) as db:
        CvService(db).process_cv(db.get(User, user_id), cv2_id)
        assert db.get(CandidateSkill, docker_id).review_status == "approved"
        assert db.get(CandidateSkill, docker_id).extracted_term_id == docker_term_id
    with Session(engine) as fresh:
        assert taxonomy_snapshot(fresh, cv1_id) == original

    with Session(engine) as db:
        outcome = RetrievalService(db).index_profile(profile_id, FakeEmbedder())
        assert outcome.outcome == "indexed"
        old_hash = outcome.source_hash
        db.commit()
        assert db.scalar(select(CandidateProfileEmbedding).where(
            CandidateProfileEmbedding.candidate_profile_id == profile_id
        )).status == "ready"
        job = Job(title="Synthetic Python role", description="Python", cleaned_description="Python", status="processed")
        db.add(job)
        db.flush()
        db.add(JobSkill(job_id=job.id, raw_text="Python", normalized_text="python", skill_type="skill",
            requirement_type="required", evidence_sentence="Python", review_status="approved"))
        db.commit()
        job_id = job.id
        assert MatchingService(db).match_my_job(db.get(User, user_id), job_id).score == 100.0
        CvService(db).delete_my_cv(db.get(User, user_id), cv1_id)
    with Session(engine) as fresh:
        assert fresh.get(CvDocument, cv1_id) is None
        assert fresh.get(CandidateSkill, docker_id).review_status == "approved"
        assert fresh.get(ExtractedCandidateTerm, docker_term_id) is not None
        assert fresh.get(CandidateSkill, manual_id) is not None
        assert not list(fresh.scalars(select(CandidateSkill).where(
            CandidateSkill.source == "extraction", CandidateSkill.extracted_term_id.is_(None),
            CandidateSkill.candidate_profile_id == profile_id,
        )))
        assert fresh.scalar(select(CandidateProfileEmbedding).where(
            CandidateProfileEmbedding.candidate_profile_id == profile_id
        )).status == "stale"
        assert not list(fresh.scalars(select(ExtractedCandidateTerm).where(
            ExtractedCandidateTerm.cv_document_id == cv1_id
        )))
        assert not list(fresh.scalars(select(TaxonomyLinkCandidate).where(
            TaxonomyLinkCandidate.extracted_term_id.in_(cv1_term_ids)
        )))
        assert not list(fresh.scalars(select(ApprovedTaxonomyLink).where(
            ApprovedTaxonomyLink.extracted_term_id.in_(cv1_term_ids)
        )))
        assert len(list(fresh.scalars(select(TaxonomyReviewEvent).where(
            TaxonomyReviewEvent.extracted_term_id.in_(cv1_term_ids)
        )))) == len(original["events"])
        assert fresh.scalar(select(CandidateJobMatch).where(
            CandidateJobMatch.candidate_profile_id == profile_id, CandidateJobMatch.job_id == job_id
        )) is None
        assert "python" not in MatchingService(fresh)._skill_sets(profile_id, job_id).candidate
        assert MatchingService(fresh).list_my_recommendations(fresh.get(User, user_id))[0].score == 0.0
        source = RetrievalRepository(fresh).profile_input(profile_id)
        assert source is not None and "Python" not in source.text and "Docker" in source.text
        refreshed = RetrievalService(fresh).index_profile(profile_id, FakeEmbedder())
        assert refreshed.outcome == "indexed" and refreshed.source_hash != old_hash
        assert RetrievalService(fresh).index_job(job_id, FakeEmbedder()).outcome == "indexed"
        fresh.commit()
        results = RetrievalService(fresh).jobs_for_user(fresh.get(User, user_id), 20)
        assert len(results) == 1 and results[0]["candidate_input_hash"] == refreshed.source_hash
    with Session(engine) as fresh:
        embedding = fresh.scalar(select(CandidateProfileEmbedding).where(
            CandidateProfileEmbedding.candidate_profile_id == profile_id
        ))
        assert embedding.status == "ready"
        assert embedding.source_hash == RetrievalRepository(fresh).profile_input(profile_id).source_hash


def test_same_cv_reprocessing_preserves_unchanged_review_and_link(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-same-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv = paste(db, user, "same.txt", "Skills\nPython\nSQL\nFastAPI")
        cv_id = cv.id
        terms, skills = document_rows(db, cv_id)
        payload = CandidateSkillReviewRequest(skills=[{
            "id": skill.id,
            "raw_text": skill.raw_text,
            "normalized_text": skill.normalized_text,
            "skill_type": skill.skill_type,
            "evidence_sentence": skill.evidence_sentence,
            "review_status": (
                "approved" if skill.normalized_text == "python"
                else "rejected" if skill.normalized_text == "sql" else "pending"
            ),
        } for skill in skills])
        SkillService(db).review_my_candidate_skills(user, payload, cv_id)
        assert {item.review_status for item in document_rows(db, cv_id)[1]} == {"approved", "rejected", "pending"}
        python = next(item for item in skills if item.normalized_text == "python")
        review_alternative(db, user, python, approve=True)
        before = taxonomy_snapshot(db, cv_id)
        assert len(before["events"]) == 2
        CvService(db).process_cv(user, cv_id)
    with Session(engine) as fresh:
        assert taxonomy_snapshot(fresh, cv_id) == before


def test_inactive_release_selection_stays_historical_after_reprocessing(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-inactive-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv = paste(db, user, "inactive.txt", "Skills\nPython")
        cv_id, profile_id = cv.id, cv.candidate_profile_id
        python = next(item for item in document_rows(db, cv_id)[1] if item.normalized_text == "python")
        python.review_status = "approved"
        db.commit()
        review_alternative(db, user, python, approve=True)
        selected = TaxonomyRepository(db).selected_link("candidate", python.extracted_term_id)
        assert selected.concept.preferred_label == "Programming"
        db.get(TaxonomyVersion, selected.concept.taxonomy_version_id).status = "inactive"
        db.commit()
        before = taxonomy_snapshot(db, cv_id)
        source = RetrievalRepository(db).profile_input(profile_id)
        assert source is not None and "Python" in source.text and "Programming" not in source.text
        CvService(db).process_cv(user, cv_id)
    with Session(engine) as fresh:
        assert taxonomy_snapshot(fresh, cv_id) == before
        source = RetrievalRepository(fresh).profile_input(profile_id)
        assert source is not None and "Programming" not in source.text


def test_cv_deletion_rolls_back_all_derived_rows(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        user = User(email=f"cv-rollback-{uuid4()}@example.com", full_name="Synthetic", hashed_password="unused")
        db.add(user)
        db.commit()
        cv = paste(db, user, "rollback.txt", "Skills\nPython")
        cv_id, user_id, profile_id = cv.id, user.id, cv.candidate_profile_id
        terms, skills = document_rows(db, cv_id)
        python = next(item for item in skills if item.normalized_text == "python")
        python.review_status = "approved"
        db.commit()
        select_ambiguous_python_for_lifecycle_test(db, user, python)
        review_alternative(db, user, python)
        job = Job(title="Synthetic Python role", description="Python", cleaned_description="Python", status="processed")
        db.add(job)
        db.flush()
        db.add(JobSkill(job_id=job.id, raw_text="Python", normalized_text="python", skill_type="skill",
            requirement_type="required", evidence_sentence="Python", review_status="approved"))
        db.commit()
        job_id = job.id
        assert MatchingService(db).match_my_job(user, job_id).score == 100.0
        assert RetrievalService(db).index_profile(profile_id, FakeEmbedder()).outcome == "indexed"
        db.commit()
        before_cv = persisted_row(cv)
        before = taxonomy_snapshot(db, cv_id)
        before_embedding = persisted_rows(db, CandidateProfileEmbedding,
            CandidateProfileEmbedding.candidate_profile_id == profile_id)
        before_match = persisted_rows(db, CandidateJobMatch,
            CandidateJobMatch.candidate_profile_id == profile_id)
        assert before["events"] and before["links"] and before_embedding and before_match

        def fail_after_delete(*args, **kwargs):
            assert not document_rows(db, cv_id)[1]
            assert not persisted_rows(db, CandidateJobMatch,
                CandidateJobMatch.candidate_profile_id == profile_id)
            embedding = db.scalar(select(CandidateProfileEmbedding).where(
                CandidateProfileEmbedding.candidate_profile_id == profile_id))
            assert embedding is not None and embedding.status == "stale"
            raise RuntimeError("injected failure after CV deletion writes")

        monkeypatch.setattr(DocumentRepository, "add_processing_log", fail_after_delete)
        with pytest.raises(RuntimeError, match="injected failure"):
            CvService(db).delete_my_cv(user, cv_id)
        db.rollback()
    with Session(engine) as fresh:
        assert persisted_row(fresh.get(CvDocument, cv_id)) == before_cv
        assert taxonomy_snapshot(fresh, cv_id) == before
        assert persisted_rows(fresh, CandidateProfileEmbedding,
            CandidateProfileEmbedding.candidate_profile_id == profile_id) == before_embedding
        assert persisted_rows(fresh, CandidateJobMatch,
            CandidateJobMatch.candidate_profile_id == profile_id) == before_match
        assert fresh.get(User, user_id) is not None

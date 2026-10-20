from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

from alembic import command
from fastapi import HTTPException
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ApprovedTaxonomyLink, CandidateProfile, CvDocument, ExtractedCandidateTerm,
    Role, TaxonomyLabel, TaxonomyLinkCandidate, User,
)
from app.db.models.taxonomy import TaxonomyReviewEvent
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.services.taxonomy_service import TaxonomyService
from app.taxonomy.normalization import normalize_taxonomy_text
from test_taxonomy import register
from test_taxonomy_postgres import pg_database, snapshot  # noqa: F401


def seed_review(db):
    repo = TaxonomyRepository(db)
    actor = User(email=f"review-{uuid4()}@example.com", full_name="Review Tester", hashed_password="unused")
    db.add(actor)
    source = repo.get_or_create_source("REVIEW_TEST", "Review Test", "", "")
    version = repo.replace_version(source, str(uuid4()), "", "test", "", True)
    concepts = [repo.add_concept(version.id, str(uuid4()), label, label.lower(), "", "skill", "en", [], {})
                for label in ("develop REST APIs", "FastAPI")]
    term_id = uuid4()
    candidates = [repo.add_link_candidate("candidate", term_id, "REST APIs", "rest apis", concept.id,
                   "fuzzy", 0.88 - index * 0.1, index + 1, "pending") for index, concept in enumerate(concepts)]
    other = repo.add_link_candidate("candidate", uuid4(), "REST APIs", "rest apis", concepts[0].id,
                                   "fuzzy", 0.88, 1, "pending")
    job = repo.add_link_candidate("job", term_id, "REST APIs", "rest apis", concepts[0].id,
                                 "fuzzy", 0.88, 1, "pending")
    db.commit()
    return actor.id, [item.id for item in candidates], other.id, job.id


@pytest.fixture(params=["sqlite", "postgres"])
def review_db(request):
    if request.param == "sqlite":
        yield request.getfixturevalue("db_session")
    else:
        engine, _, _ = request.getfixturevalue("pg_database")
        with Session(engine) as db:
            yield db


def assert_consistent(db, term_source, term_id, selected_id):
    # A new session avoids assertions against the writer's identity map.
    with Session(db.bind) as fresh:
        repo = TaxonomyRepository(fresh)
        rows = repo.term_candidates(term_source, term_id)
        link = repo.selected_link(term_source, term_id)
        assert (link.link_candidate_id if link else None) == selected_id
        assert {row.id for row in rows if row.review_status == "approved"} == ({selected_id} if selected_id else set())


def review(db, candidate_id, actor_id, status="approved", replace=False, token=None):
    return TaxonomyService(db).review_link(candidate_id, status, None, db.get(User, actor_id), replace, token)


def selection_token(db, candidate_id):
    candidate = db.get(TaxonomyLinkCandidate, candidate_id)
    link = TaxonomyRepository(db).selected_link(candidate.term_source, candidate.extracted_term_id)
    return TaxonomyService._selection_token(link)


def test_approve_replace_requires_confirmation_and_supersedes(review_db):
    db = review_db
    actor, (a, b), _, _ = seed_review(db)
    review(db, a, actor)
    with pytest.raises(HTTPException) as error:
        review(db, b, actor)
    assert error.value.status_code == 409
    assert db.get(TaxonomyLinkCandidate, b).review_status == "pending"
    token = selection_token(db, a)
    review(db, b, actor, replace=True, token=token)
    assert db.get(TaxonomyLinkCandidate, a).review_status == "superseded"
    assert_consistent(db, "candidate", db.get(TaxonomyLinkCandidate, a).extracted_term_id, b)
    with Session(db.bind) as fresh:
        events = list(fresh.scalars(select(TaxonomyReviewEvent).where(TaxonomyReviewEvent.candidate_id.in_([a, b])).order_by(TaxonomyReviewEvent.created_at)))
        assert [item.action for item in events] == ["approved", "replaced"]
        assert events[-1].before_state["selection"]["candidate_id"] == str(a)
        assert events[-1].after_state["selection"]["candidate_id"] == str(b)
        assert events[-1].reviewer_id == actor
    with pytest.raises(HTTPException) as error:
        review(db, a, actor, replace=True, token=token)
    assert error.value.status_code == 409


def test_reject_selected_and_repeat_are_idempotent(review_db):
    db = review_db
    actor, (a, _), _, _ = seed_review(db)
    review(db, a, actor)
    review(db, a, actor)
    term = db.get(TaxonomyLinkCandidate, a).extracted_term_id
    assert db.scalar(select(func.count()).select_from(TaxonomyReviewEvent).where(TaxonomyReviewEvent.extracted_term_id == term)) == 1
    review(db, a, actor, "rejected")
    assert_consistent(db, "candidate", term, None)
    timestamp = db.get(TaxonomyLinkCandidate, a).reviewed_at
    review(db, a, actor, "rejected")
    assert db.get(TaxonomyLinkCandidate, a).reviewed_at == timestamp
    assert db.scalar(select(func.count()).select_from(TaxonomyReviewEvent).where(TaxonomyReviewEvent.extracted_term_id == term)) == 2
    review(db, a, actor)
    assert_consistent(db, "candidate", term, a)


def test_reject_alternative_preserves_selection_and_isolation(review_db):
    db = review_db
    actor, (a, b), other, job = seed_review(db)
    for candidate_id in (a, other, job):
        review(db, candidate_id, actor)
    review(db, b, actor, "rejected")
    for source, candidate_id in (("candidate", a), ("candidate", other), ("job", job)):
        assert_consistent(db, source, db.get(TaxonomyLinkCandidate, candidate_id).extracted_term_id, candidate_id)
    assert db.get(TaxonomyLinkCandidate, b).review_status == "rejected"


def test_legacy_inconsistency_read_only_until_explicit_review(review_db):
    db = review_db
    actor, (a, b), _, _ = seed_review(db)
    review(db, b, actor)
    legacy = db.get(TaxonomyLinkCandidate, a)
    legacy.review_status = "approved"
    legacy.reviewed_by = actor
    legacy.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    service = TaxonomyService(db)
    group = service.review_groups("selected", str(legacy.extracted_term_id), 20, 0).items[0]
    assert group.inconsistent
    assert group.selection.candidate_id == b
    assert db.get(TaxonomyLinkCandidate, a).review_status == "approved"
    pending = service.review_groups("pending", str(legacy.extracted_term_id), 20, 0).items
    assert [item.term_source for item in pending] == ["job"]
    review(db, a, actor, replace=True, token=group.selection.token)
    assert_consistent(db, "candidate", legacy.extracted_term_id, a)
    assert db.get(TaxonomyLinkCandidate, b).review_status == "superseded"
    assert not service.review_groups("selected", str(legacy.extracted_term_id), 20, 0).items[0].inconsistent


def test_audit_failure_rolls_back_whole_review(review_db, monkeypatch):
    db = review_db
    actor, (a, b), _, _ = seed_review(db)
    review(db, a, actor)
    token = selection_token(db, a)

    def fail(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(TaxonomyRepository, "record_review", fail)
    with pytest.raises(RuntimeError, match="audit write failed"):
        review(db, b, actor, replace=True, token=token)
    assert_consistent(db, "candidate", db.get(TaxonomyLinkCandidate, a).extracted_term_id, a)
    assert db.get(TaxonomyLinkCandidate, b).review_status == "pending"


@pytest.mark.parametrize("role", ["admin", "researcher", "candidate"])
def test_review_api_permissions_and_revisit(client, db_session, role):
    db = db_session
    token = register(client, f"{role}-review@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    user = db.scalar(select(User).where(User.email == f"{role}-review@example.com"))
    if role != "candidate":
        user.roles.append(Role(name=role, description=role))
        db.commit()
    _, (a, b), _, _ = seed_review(db)
    term_id = db.get(TaxonomyLinkCandidate, a).extracted_term_id
    list_path = f"/taxonomy/reviews?state=all&q={term_id}"
    history_path = f"/taxonomy/reviews/candidate/{term_id}/history"
    expected = 403 if role == "candidate" else 200
    assert client.get(list_path, headers=headers).status_code == expected
    assert client.get(history_path, headers=headers).status_code == expected
    assert client.put(f"/taxonomy/link/{a}/approve", headers=headers, json={"status": "approved"}).status_code == expected
    if role == "candidate":
        assert client.put(f"/taxonomy/link/{a}/approve", headers=headers, json={"status": "rejected"}).status_code == 403
        return
    group = client.get(list_path, headers=headers).json()["items"][0]
    assert group["selection"]["candidate_id"] == str(a)
    assert len(group["candidates"]) == 2
    assert client.put(f"/taxonomy/link/{b}/approve", headers=headers, json={"status": "approved"}).status_code == 409
    assert client.put(f"/taxonomy/link/{b}/approve", headers=headers, json={"status": "approved", "replace_selection": True,
        "expected_selection_token": group["selection"]["token"]}).status_code == 200
    assert client.put(f"/taxonomy/link/{b}/approve", headers=headers, json={"status": "rejected"}).status_code == 200
    assert len(client.get(history_path, headers=headers).json()) == 3


def test_concurrent_approvals_cannot_silently_replace(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        actor, (a, b), _, _ = seed_review(db)
    barrier = Barrier(2)

    def approve(candidate_id):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                review(db, candidate_id, actor)
                return 200, candidate_id
            except HTTPException as exc:
                return exc.status_code, candidate_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, (a, b)))
    assert sorted(status for status, _ in results) == [200, 409]
    winner = next(candidate_id for status, candidate_id in results if status == 200)
    with Session(engine) as db:
        assert_consistent(db, "candidate", db.get(TaxonomyLinkCandidate, a).extracted_term_id, winner)


def test_upgrade_0006_does_not_repair_existing_review_rows(pg_database):
    engine, config, _ = pg_database
    command.downgrade(config, "0006_official_taxonomy")
    with Session(engine) as db:
        actor, (a, b), _, _ = seed_review(db)
        repo = TaxonomyRepository(db)
        repo.approve_candidate(db.get(TaxonomyLinkCandidate, b), "human_review", actor)
        db.get(TaxonomyLinkCandidate, a).review_status = "approved"
        db.commit()
    with engine.connect() as connection:
        before = snapshot(connection)
    command.upgrade(config, "head")
    with engine.connect() as connection:
        after = snapshot(connection)
    assert after.pop("taxonomy_review_events") == []
    assert after.pop("candidate_profile_embeddings") == []
    assert after.pop("job_embeddings") == []
    assert before == after


def seed_linkable_cv(db: Session, text: str) -> tuple[User, CvDocument, ExtractedCandidateTerm]:
    actor = User(email=f"link-{uuid4()}@example.com", full_name="Link Reviewer", hashed_password="unused")
    db.add(actor)
    db.flush()
    profile = CandidateProfile(user_id=actor.id, consent_to_process_cv=True)
    db.add(profile)
    db.flush()
    document = CvDocument(
        candidate_profile_id=profile.id, original_filename="synthetic.txt", content_type="text/plain",
        source="paste", raw_text=text, cleaned_text=text,
    )
    db.add(document)
    db.flush()
    term = ExtractedCandidateTerm(
        cv_document_id=document.id, raw_text=text, normalized_text=normalize_taxonomy_text(text),
        term_type="skill", source_section="skills", evidence_sentence=text,
        extraction_method="test", confidence_score=0.9, start_char=0, end_char=len(text),
    )
    db.add(term)
    db.commit()
    return actor, document, term


def test_automatic_linking_requires_unique_top_concept_in_postgres(pg_database, monkeypatch):
    engine, _, _ = pg_database
    with Session(engine) as db:
        repo = TaxonomyRepository(db)
        source = repo.get_or_create_source("AMBIGUITY_TEST", "Ambiguity Test", "", "")
        version = repo.replace_version(source, "1", "", "test", "", True)

        def concept(preferred: str, *alternatives: str):
            return repo.add_concept(
                version.id, str(uuid4()), preferred, normalize_taxonomy_text(preferred), "", "skill", "en",
                [(label, normalize_taxonomy_text(label)) for label in alternatives], {},
            )

        concept("BatchFiveUniquePreferred")
        concept("Unrelated unique", "BatchFiveUniqueAlias")
        for _ in range(2):
            concept("BatchFiveTiedPreferred")
        concept("Alternative one", "BatchFiveTiedAlias")
        concept("Alternative two", "BatchFiveTiedAlias")
        concept("BatchFivePriority")
        concept("Priority alternative", "BatchFivePriority")
        duplicated = concept("Duplicated label owner", "BatchFiveDuplicate")
        duplicated.labels.append(TaxonomyLabel(
            label="BatchFiveDuplicate", normalized_label=normalize_taxonomy_text("BatchFiveDuplicate"),
            label_type="other", language="en",
        ))
        db.commit()

        cases = [
            ("BatchFiveUniquePreferred", True, "exact_preferred", 1.0),
            ("BatchFiveUniqueAlias", True, "exact_alternative", 0.98),
            ("BatchFiveTiedPreferred", False, "exact_preferred", 1.0),
            ("BatchFiveTiedAlias", False, "exact_alternative", 0.98),
            ("BatchFivePriority", True, "exact_preferred", 1.0),
            ("Pythn", False, "fuzzy", None),
            ("BatchFiveDuplicate", True, "exact_alternative", 0.98),
            ("Python", False, "exact_preferred", 1.0),
        ]
        ids = {}
        for text, should_approve, method, confidence in cases:
            actor, document, term = seed_linkable_cv(db, text)
            run = TaxonomyService(db).link_document("candidate", document.id)
            ids[text] = (actor.id, term.id)
            assert run.links_auto_approved == int(should_approve)
            with Session(engine) as fresh:
                candidates = TaxonomyRepository(fresh).term_candidates("candidate", term.id)
                selected = TaxonomyRepository(fresh).selected_link("candidate", term.id)
                assert candidates and candidates[0].match_method == method
                assert (selected is not None) is should_approve
                assert {item.review_status for item in candidates if item.confidence_score == candidates[0].confidence_score} == {
                    "approved" if should_approve else "pending"
                }
                if confidence is not None:
                    assert candidates[0].confidence_score == confidence
                else:
                    assert candidates[0].confidence_score < 0.95

        _, reverse_document, reverse_term = seed_linkable_cv(db, "BatchFiveTiedPreferred")
        original = TaxonomyRepository.active_concepts
        monkeypatch.setattr(TaxonomyRepository, "active_concepts", lambda self: list(reversed(original(self))))
        reverse_run = TaxonomyService(db).link_document("candidate", reverse_document.id)
        assert reverse_run.links_auto_approved == 0
        with Session(engine) as fresh:
            candidates = TaxonomyRepository(fresh).term_candidates("candidate", reverse_term.id)
            assert {item.review_status for item in candidates if item.confidence_score == 1.0} == {"pending"}
            assert TaxonomyRepository(fresh).selected_link("candidate", reverse_term.id) is None

        actor_id, tied_term_id = ids["Python"]
        pending = repo.term_candidates("candidate", tied_term_id)
        TaxonomyService(db).review_link(pending[0].id, "approved", None, db.get(User, actor_id))
        with Session(engine) as fresh:
            selected = TaxonomyRepository(fresh).selected_link("candidate", tied_term_id)
            assert selected and selected.link_candidate_id == pending[0].id
            assert selected.approval_source == "human_review"
            assert fresh.scalar(select(func.count()).select_from(TaxonomyReviewEvent).where(
                TaxonomyReviewEvent.extracted_term_id == tied_term_id
            )) == 1


def test_new_ambiguity_rule_does_not_rewrite_other_selection_or_audit(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        actor, document, term = seed_linkable_cv(db, "Python")
        concept = TaxonomyRepository(db).active_concepts()[0]
        prior_term = uuid4()
        prior_candidate = TaxonomyRepository(db).add_link_candidate(
            "candidate", prior_term, "Python", "python", concept.id,
            "exact_preferred", 1.0, 1, "pending",
        )
        db.commit()
        TaxonomyService(db).review_link(prior_candidate.id, "approved", None, actor)
        with Session(engine) as fresh:
            before_link = TaxonomyRepository(fresh).selected_link("candidate", prior_term)
            before = (before_link.id, before_link.link_candidate_id, before_link.concept_id,
                      before_link.approval_source, before_link.approved_at)
            events_before = [(item.id, item.action, item.before_state, item.after_state) for item in fresh.scalars(
                select(TaxonomyReviewEvent).where(TaxonomyReviewEvent.extracted_term_id == prior_term)
            )]
        assert TaxonomyService(db).link_document("candidate", document.id).links_auto_approved == 0
        with Session(engine) as fresh:
            after_link = TaxonomyRepository(fresh).selected_link("candidate", prior_term)
            assert (after_link.id, after_link.link_candidate_id, after_link.concept_id,
                    after_link.approval_source, after_link.approved_at) == before
            assert [(item.id, item.action, item.before_state, item.after_state) for item in fresh.scalars(
                select(TaxonomyReviewEvent).where(TaxonomyReviewEvent.extracted_term_id == prior_term)
            )] == events_before
            assert TaxonomyRepository(fresh).selected_link("candidate", term.id) is None

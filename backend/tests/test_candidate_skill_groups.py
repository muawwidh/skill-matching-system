from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.models import CandidateSkill, ExtractedCandidateTerm, User
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import DocumentRepository
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.schemas.documents import CandidateSkillReviewRequest
from app.services.skill_service import SkillService
from app.services.taxonomy_service import TaxonomyService
from test_taxonomy_postgres import pg_database  # noqa: F401


@pytest.fixture(params=["sqlite", "postgres"])
def group_db(request):
    if request.param == "sqlite":
        yield request.getfixturevalue("db_session")
    else:
        engine, _, _ = request.getfixturevalue("pg_database")
        with Session(engine) as db:
            yield db


def seed(db):
    user = User(email=f"groups-{uuid4()}@example.com", full_name="Group Tester", hashed_password="unused")
    db.add(user)
    db.flush()
    repo = DocumentRepository(db)
    profile = repo.get_or_create_candidate_profile(user.id)
    cv = repo.create_cv_document(profile.id, "test.txt", "text/plain", "paste", "", "", 0)
    rows = []
    for index, status in enumerate(("pending", "approved", "rejected")):
        term = ExtractedCandidateTerm(cv_document_id=cv.id, raw_text="FastAPI", normalized_text="fastapi",
            term_type="tool", evidence_sentence=f"Evidence {index}", extraction_method="test")
        db.add(term)
        db.flush()
        skill = CandidateSkill(candidate_profile_id=profile.id, extracted_term_id=term.id,
            raw_text=term.raw_text, normalized_text=term.normalized_text, skill_type=term.term_type,
            evidence_sentence=term.evidence_sentence, confidence_score=.9, review_status=status, source="extraction")
        db.add(skill)
        rows.append(skill)
    taxonomy = TaxonomyRepository(db)
    source = taxonomy.get_or_create_source("GROUP_TEST", "Group test", "", "")
    concepts = []
    for version_name in ("one", "two"):
        version = taxonomy.replace_version(source, version_name, "", "fixture", "", True)
        for _ in range(2):
            concepts.append(taxonomy.add_concept(version.id, str(uuid4()), "FastAPI", "fastapi", "", "skill", "en", [], {}))
    db.commit()
    return user, cv, rows, concepts


def link(db, row, concept):
    repo = TaxonomyRepository(db)
    candidate = repo.add_link_candidate("candidate", row.extracted_term_id, row.raw_text, row.normalized_text,
        concept.id, "exact_preferred", 1, 1, "pending")
    repo.approve_candidate(candidate, "test", None)
    db.commit()
    return candidate


def test_group_occurrences_aliases_and_mixed_reviews(group_db):
    db = group_db
    user, cv, rows, concepts = seed(db)
    rows[1].raw_text = "Fast API alias"
    rows[1].normalized_text = "fast api alias"
    term = db.get(ExtractedCandidateTerm, rows[1].extracted_term_id)
    term.raw_text, term.normalized_text = rows[1].raw_text, rows[1].normalized_text
    for row in rows:
        link(db, row, concepts[0])
    groups = SkillService(db).grouped_cv_skills(user, cv.id)
    assert len(groups) == 1
    assert groups[0].taxonomy.release_id == concepts[0].taxonomy_version_id
    assert {item.id for item in groups[0].occurrences} == {row.id for row in rows}
    assert {item.evidence_sentence for item in groups[0].occurrences} == {f"Evidence {i}" for i in range(3)}
    assert {item.review_status for item in groups[0].occurrences} == {"pending", "approved", "rejected"}
    for row in rows:
        row.review_status = "rejected"
    db.commit()
    assert all(item.review_status == "rejected" for item in SkillService(db).grouped_cv_skills(user, cv.id)[0].occurrences)


def test_same_labels_different_concepts_releases_and_link_states(group_db):
    db = group_db
    user, cv, rows, concepts = seed(db)
    link(db, rows[0], concepts[0])
    link(db, rows[1], concepts[1])
    assert len(SkillService(db).grouped_cv_skills(user, cv.id)) == 3
    link(db, rows[2], concepts[2])
    groups = SkillService(db).grouped_cv_skills(user, cv.id)
    assert len({group.key for group in groups}) == 3
    assert len({group.taxonomy.release_id for group in groups}) == 2


def test_unlinked_fallback_is_exact_normalization_and_type(group_db):
    db = group_db
    user, cv, rows, _ = seed(db)
    assert len(SkillService(db).grouped_cv_skills(user, cv.id)) == 1
    rows[1].skill_type = "skill"
    rows[2].normalized_text = "fast api"
    db.commit()
    groups = SkillService(db).grouped_cv_skills(user, cv.id)
    assert len(groups) == 3
    assert all(group.taxonomy is None for group in groups)


def test_edit_save_reload_invalidates_only_corrected_mapping(group_db):
    db = group_db
    user, cv, rows, concepts = seed(db)
    for row in rows:
        link(db, row, concepts[0])
    service = SkillService(db)
    payload = [item.model_dump() for item in service.grouped_cv_skills(user, cv.id)[0].occurrences]
    target = next(item for item in payload if item["id"] == rows[0].id)
    target.update(raw_text="Django", normalized_text="django", review_status="approved")
    service.review_my_candidate_skills(user, CandidateSkillReviewRequest(skills=payload), cv.id)
    with Session(db.bind) as fresh:
        groups = SkillService(fresh).grouped_cv_skills(fresh.get(User, user.id), cv.id)
        assert sorted(len(group.occurrences) for group in groups) == [1, 2]
        corrected = next(group for group in groups if group.taxonomy is None)
        assert corrected.label == "django"
        assert corrected.occurrences[0].id == rows[0].id
        assert corrected.occurrences[0].evidence_sentence == "Evidence 0"
        term = fresh.get(ExtractedCandidateTerm, rows[0].extracted_term_id)
        assert term.normalized_text == "django"
        assert TaxonomyRepository(fresh).selected_link("candidate", term.id) is None


def test_grouping_refreshes_after_taxonomy_replacement(group_db):
    db = group_db
    user, cv, rows, concepts = seed(db)
    for row in rows:
        link(db, row, concepts[0])
    repo = TaxonomyRepository(db)
    replacement = repo.add_link_candidate("candidate", rows[0].extracted_term_id, "FastAPI", "fastapi",
        concepts[2].id, "fuzzy", .7, 2, "pending")
    db.commit()
    token = TaxonomyService._selection_token(repo.selected_link("candidate", rows[0].extracted_term_id))
    TaxonomyService(db).review_link(replacement.id, "approved", None, user, True, token)
    with Session(db.bind) as fresh:
        groups = SkillService(fresh).grouped_cv_skills(fresh.get(User, user.id), cv.id)
        assert sorted(len(group.occurrences) for group in groups) == [1, 2]


def test_group_api_ownership_and_cv_save_scope(group_db):
    db = group_db
    user, cv, rows, _ = seed(db)
    other, other_cv, other_rows, _ = seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: other
    with TestClient(app) as client:
        assert client.get(f"/cvs/{cv.id}/skill-groups").status_code == 404
        assert client.get(f"/cvs/{cv.id}/extracted-skills").status_code == 404
        payload = {"skills": [{"id": str(rows[0].id), "raw_text": "stolen", "normalized_text": "stolen"}]}
        assert client.put(f"/cvs/{other_cv.id}/extracted-skills", json=payload).status_code == 404
        response = client.get(f"/cvs/{other_cv.id}/skill-groups")
        assert response.status_code == 200
        assert "reviewer" not in response.text
        assert str(rows[0].id) not in response.text
    repo = DocumentRepository(db)
    same_owner_cv = repo.create_cv_document(cv.candidate_profile_id, "second.txt", "text/plain", "paste", "", "", 0)
    db.commit()
    with pytest.raises(HTTPException) as error:
        SkillService(db).review_my_candidate_skills(user, CandidateSkillReviewRequest(skills=payload["skills"]), same_owner_cv.id)
    assert error.value.status_code == 404


def test_status_only_review_preserves_mapping_and_legacy_edit_is_unlinked(group_db):
    db = group_db
    user, cv, rows, concepts = seed(db)
    for row in rows:
        link(db, row, concepts[0])
    service = SkillService(db)
    payload = [item.model_dump() for item in service.grouped_cv_skills(user, cv.id)[0].occurrences]
    for item in payload:
        item["review_status"] = "rejected"
    service.review_my_candidate_skills(user, CandidateSkillReviewRequest(skills=payload), cv.id)
    group = service.grouped_cv_skills(user, cv.id)[0]
    assert group.taxonomy is not None
    assert all(item.review_status == "rejected" for item in group.occurrences)
    rows[0].raw_text = "Legacy correction"
    db.commit()
    groups = service.grouped_cv_skills(user, cv.id)
    assert len(groups) == 2
    assert next(group for group in groups if group.taxonomy is None).occurrences[0].id == rows[0].id

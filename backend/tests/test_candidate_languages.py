"""Candidate languages: CV language rule, My profile add/remove/review, name-only job comparison.

Profile languages (language rule or added on My profile) never enter the matching
profile embedding or the skill coverage; skills typed "language" earlier keep their
former behaviour but still count as the candidate's languages.
"""
import json
from uuid import UUID

from sqlalchemy import select

from app.db.models import CandidateProfile, CandidateSkill, CvDocument, ExtractedCandidateTerm, User
from app.nlp.skill_extractor import SkillExtractor
from app.repositories.retrieval_repository import RetrievalRepository
from app.services import language_backfill
from app.services.section_detection_service import SectionDetectionService
from tests.test_recommendations import create_job, manager, register

URL = "/candidates/me/languages"


def _extract(text: str):
    return SkillExtractor().extract_from_sections(SectionDetectionService().detect(text), text, "candidate")


def _paste(client, headers, text):
    response = client.post("/cvs/paste", headers=headers, json={
        "text": text, "original_filename": "cv.txt", "consent_to_process": True})
    assert response.status_code == 201
    return response.json()["id"]


def _profile_id(db_session, email):
    user = db_session.scalar(select(User).where(User.email == email))
    return db_session.scalar(select(CandidateProfile.id).where(CandidateProfile.user_id == user.id))


def test_cv_language_rule_finds_listed_and_cued_languages_only():
    terms = _extract("Skills\nPython, SQL\n\nLanguages\nEnglish (C1), German - native\n\n"
                     "Experience\nTaught French history. Fluent Spanish.")
    languages = [(t.normalized_text, t.extraction_method) for t in terms if t.term_type == "language"]
    assert languages == [("english", "language_rule@v4"), ("german", "language_rule@v4"),
                         ("spanish", "language_rule@v4")]
    # The other CV terms keep the v2 contract.
    assert {t.extraction_method for t in terms if t.term_type != "language"} == {"dictionary@v2"}


def test_new_upload_lists_cv_languages_pending_and_candidate_confirms_them(client):
    headers = register(client, "candidate@example.com")
    _paste(client, headers, "Skills\nPython\n\nLanguages\nEnglish, German\n")
    languages = client.get(URL, headers=headers).json()
    assert [(l["label"], l["status"], l["origin"]) for l in languages] == [
        ("English", "pending", "cv"), ("German", "pending", "cv")]
    english, german = languages
    assert client.put(f"{URL}/{english['id']}/review", headers=headers,
                      json={"decision": "approved"}).json()["status"] == "approved"
    assert client.put(f"{URL}/{german['id']}/review", headers=headers,
                      json={"decision": "rejected"}).status_code == 200
    assert [(l["label"], l["status"]) for l in client.get(URL, headers=headers).json()] == [("English", "approved")]
    # A CV language is rejected, never deleted, so the decision stays stored.
    assert client.delete(f"{URL}/{german['id']}", headers=headers).status_code == 404
    # Profile languages are not counted as matching-profile skills.
    profile = client.get("/candidates/me/matching-profile", headers=headers).json()
    assert sum(profile["cvs"][0]["skills"].values()) == 1  # python only


def test_add_and_remove_languages_with_optional_level(client, db_session):
    headers = register(client, "candidate@example.com")
    added = client.post(URL, headers=headers, json={"name": "  german ", "level": "B2"})
    assert added.status_code == 201
    body = added.json()
    assert (body["label"], body["name"], body["level"], body["status"], body["origin"]) == (
        "German", "german", "B2", "approved", "added")
    assert client.post(URL, headers=headers, json={"name": "German"}).status_code == 409
    assert client.post(URL, headers=headers, json={"name": "French", "level": "fluent"}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "French"}).json()["level"] is None
    other = register(client, "other@example.com")
    assert client.delete(f"{URL}/{body['id']}", headers=other).status_code == 404
    assert client.delete(f"{URL}/{body['id']}", headers=headers).status_code == 204
    assert [l["label"] for l in client.get(URL, headers=headers).json()] == ["French"]
    # Not shown among the skills added by hand.
    assert client.get("/candidates/me/manual-skills", headers=headers).json() == []
    staff = manager(client, db_session)
    assert client.post(URL, headers=staff, json={"name": "German"}).status_code == 403


def test_profile_languages_stay_out_of_the_embedding_but_old_language_skills_stay_in(client, db_session):
    headers = register(client, "candidate@example.com")
    cv_id = _paste(client, headers, "Skills\nPython\n\nLanguages\nEnglish\n")
    skills = [s for s in client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
              if s["skill_type"] != "language"]
    for skill in skills:
        skill["review_status"] = "approved"
    assert client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": skills}).status_code == 200
    profile_id = _profile_id(db_session, "candidate@example.com")
    repository = RetrievalRepository(db_session)
    before = repository.profile_input(profile_id)
    assert "english" not in before.text.lower()
    for language in client.get(URL, headers=headers).json():
        client.put(f"{URL}/{language['id']}/review", headers=headers, json={"decision": "approved"})
    client.post(URL, headers=headers, json={"name": "German", "level": "C1"})
    db_session.expire_all()
    assert repository.profile_input(profile_id).source_hash == before.source_hash
    # A skill typed "language" in the skill editor (before profile languages existed) stays in.
    db_session.add(CandidateSkill(candidate_profile_id=profile_id, raw_text="Italian", normalized_text="italian",
                                  skill_type="language", review_status="approved", source="manual_review"))
    db_session.commit()
    assert "italian" in repository.profile_input(profile_id).text.lower()


def test_job_card_compares_languages_by_name_outside_skill_counts(client, db_session):
    staff = manager(client, db_session)
    job_id = create_job(client, staff, "Data Engineer", "Python\nFluent English and German are required.")
    headers = register(client, "candidate@example.com")
    cv_id = _paste(client, headers, "Skills\nPython\n")
    skills = client.get(f"/cvs/{cv_id}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = "approved"
    client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": skills})

    # No confirmed language: nothing compared, the languages stay "not assessed" with a hint.
    body = client.get(f"/matches/jobs/{job_id}", headers=headers).json()
    assert body["languages"] == {"compared": False, "matched": [], "missing": [],
                                 "note": "Add your languages on My profile to compare."}
    assert {"english", "german"} <= set(body["not_assessed_required"])
    required_total = len(body["matched_required"]) + len(body["missing_required"])

    client.post(URL, headers=headers, json={"name": "English", "level": "C2"})
    body = client.get(f"/matches/jobs/{job_id}", headers=headers).json()
    assert body["languages"]["compared"] is True
    assert [e["label"] for e in body["languages"]["matched"]] == ["English"]
    assert [e["label"] for e in body["languages"]["missing"]] == ["German"]
    assert all(e["requirement"] == "required" for e in body["languages"]["matched"] + body["languages"]["missing"])
    assert not {"english", "german"} & set(body["not_assessed_required"])
    assert len(body["matched_required"]) + len(body["missing_required"]) == required_total  # skill counts unchanged
    assert "Languages: 1 of 2 matched by name" in body["explanation"]
    assert "not found in your profile: German" in body["explanation"]


def test_old_language_typed_skills_count_as_confirmed_languages(client, db_session):
    staff = manager(client, db_session)
    job_id = create_job(client, staff, "Analyst", "SQL\nFluent German is required.")
    headers = register(client, "candidate@example.com")
    client.get(URL, headers=headers)  # creates the profile
    profile_id = _profile_id(db_session, "candidate@example.com")
    db_session.add(CandidateSkill(candidate_profile_id=profile_id, raw_text="German", normalized_text="german",
                                  skill_type="language", review_status="approved", source="manual_review"))
    db_session.commit()
    body = client.get(f"/matches/jobs/{job_id}", headers=headers).json()
    assert [e["label"] for e in body["languages"]["matched"]] == ["German"]
    assert [l["origin"] for l in client.get(URL, headers=headers).json()] == ["skill_editor"]


def test_backfill_adds_languages_additively_and_skips_excluded_users(client, db_session, tmp_path):
    kept = register(client, "kept@example.com")
    skipped = register(client, "skipped@example.com")
    _paste(client, kept, "Skills\nPython\n")
    _paste(client, skipped, "Skills\nPython\n")
    # Simulate CVs processed before the language rule: append a language block to the stored text.
    for document in db_session.scalars(select(CvDocument)):
        document.cleaned_text += "\n\nLanguages\nEnglish, Polish\n"
    db_session.commit()
    before = {(s.id, s.review_status) for s in db_session.scalars(select(CandidateSkill))}
    skipped_user = db_session.scalar(select(User).where(User.email == "skipped@example.com"))
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"candidates": {"C1": str(skipped_user.id)}, "jobs": {}}))
    users = language_backfill.excluded_users(mapping)

    dry = language_backfill.backfill(db_session, users)
    assert (dry["cvs"], dry["excluded_cvs"], dry["languages_added"]) == (1, 1, 2)
    assert {(s.id, s.review_status) for s in db_session.scalars(select(CandidateSkill))} == before

    applied = language_backfill.backfill(db_session, users, apply=True)
    assert applied["languages_added"] == 2
    after = list(db_session.scalars(select(CandidateSkill)))
    assert before <= {(s.id, s.review_status) for s in after}  # nothing changed or removed
    new = [s for s in after if (s.id, s.review_status) not in before]
    assert sorted(s.normalized_text for s in new) == ["english", "polish"]
    assert {s.review_status for s in new} == {"pending"}
    assert {s.candidate_profile_id for s in new} == {_profile_id(db_session, "kept@example.com")}
    assert language_backfill.backfill(db_session, users, apply=True)["languages_added"] == 0  # idempotent
    methods = set(db_session.scalars(select(ExtractedCandidateTerm.extraction_method).where(
        ExtractedCandidateTerm.id.in_([s.extracted_term_id for s in new]))))
    assert methods == {"language_rule@v4"}

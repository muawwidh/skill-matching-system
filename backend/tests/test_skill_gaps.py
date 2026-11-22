"""Dashboard read-only endpoints: skill gaps over the top 10, the live job pool, manual skills, not-assessed lists."""
from datetime import datetime, timezone

from app.db.models import ProcessingLog
from app.services.job_import_service import IMPORT_ENTITY
from tests.test_recommendations import candidate_with_skills, create_job, manager, register


def test_skill_gaps_count_required_missing_skills_across_the_top_results(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    create_job(client, staff, "Data engineer", "Required: Python, Kubernetes, Terraform")
    create_job(client, staff, "Platform engineer", "Required: Python, Kubernetes")
    create_job(client, staff, "Analyst", "Required: Python, Excel")
    headers = candidate_with_skills(client)

    recommendations = client.get("/matches/recommendations", headers=headers).json()
    body = client.get("/matches/skill-gaps", headers=headers).json()
    assert body["status"] == "ready" and body["of"] == len(recommendations["results"]) == 3
    expected: dict[str, int] = {}
    for item in recommendations["results"]:
        for label in {m["label"] for m in item["missing_required"]}:
            expected[label] = expected.get(label, 0) + 1
    assert {gap["label"]: gap["missing_in"] for gap in body["gaps"]} == expected
    assert [gap["missing_in"] for gap in body["gaps"]] == sorted((g["missing_in"] for g in body["gaps"]), reverse=True)
    assert body["gaps"][0]["missing_in"] >= 2


def test_skill_gaps_are_empty_without_results_and_candidate_only(client, db_session, fake_retrieval):
    headers = register(client, "new@example.com")
    assert client.get("/matches/skill-gaps", headers=headers).json() == {
        "status": "profile_not_ready", "of": 0, "gaps": []}
    staff = manager(client, db_session)
    assert client.get("/matches/skill-gaps", headers=staff).status_code == 403
    assert client.get("/matches/job-pool", headers=staff).status_code == 403


def test_job_pool_counts_live_jobs_and_the_last_successful_import(client, db_session):
    headers = register(client, "candidate@example.com")
    assert client.get("/matches/job-pool", headers=headers).json() == {"live_jobs": 0, "last_import_at": None}
    staff = manager(client, db_session)
    create_job(client, staff, "Manual job", "Required: Python")  # manual jobs are not live
    from uuid import uuid4
    for status, day in (("success", 20), ("failed", 22), ("partial", 21)):
        db_session.add(ProcessingLog(entity_type=IMPORT_ENTITY, entity_id=uuid4(), stage="live_import", status=status,
                                     message="", metadata_json={},
                                     created_at=datetime(2026, 11, day, 12, tzinfo=timezone.utc)))
    db_session.commit()
    body = client.get("/matches/job-pool", headers=headers).json()
    assert body["live_jobs"] == 0 and body["last_import_at"].startswith("2026-11-21")


def test_manual_skills_list_only_skills_added_by_hand(client, db_session):
    headers = register(client, "candidate@example.com")
    client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython, SQL", "original_filename": "cv.txt", "consent_to_process": True})
    cv_id = client.get("/cvs", headers=headers).json()[0]["id"]
    assert client.get("/candidates/me/manual-skills", headers=headers).json() == []
    client.put(f"/cvs/{cv_id}/extracted-skills", headers=headers, json={"skills": [
        {"raw_text": "Kubernetes", "normalized_text": "kubernetes", "review_status": "approved"}]})
    manual = client.get("/candidates/me/manual-skills", headers=headers).json()
    assert [(s["raw_text"], s["source"]) for s in manual] == [("Kubernetes", "manual_review")]
    staff = manager(client, db_session)
    assert client.get("/candidates/me/manual-skills", headers=staff).status_code == 403


def test_recommendations_list_not_assessed_terms(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    create_job(client, staff, "Engineer", "Required: Python. Bachelor degree in computer science required.")
    headers = candidate_with_skills(client)
    item = client.get("/matches/recommendations", headers=headers).json()["results"][0]
    assert item["not_assessed_required"], item["explanation"]
    for label in item["not_assessed_required"]:
        assert label in item["explanation"]


def test_recommendations_show_the_stated_minimum_even_without_work_entries(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    create_job(client, staff, "Engineer", "Required: Python. At least 3 years of experience.")
    create_job(client, staff, "Other", "Required: Python.")
    headers = candidate_with_skills(client)
    results = client.get("/matches/recommendations", headers=headers).json()["results"]
    by_title = {item["job"]["title"]: item for item in results}
    assert by_title["Engineer"]["min_required_years"] == 3 and by_title["Engineer"]["related_experience"] is None
    assert by_title["Other"]["min_required_years"] is None

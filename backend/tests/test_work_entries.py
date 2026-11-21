"""Candidate work entries (D060): CRUD, validation, CV pre-fill, candidate-only, account deletion."""
from datetime import date

from sqlalchemy import func, select

from app.db.models import CandidateWorkEntry
from app.matching.work_history import detect_entries
from tests.esco_occupations import add_esco_occupations
from tests.test_recommendations import manager, register


def _paste_cv(client, headers, text):
    response = client.post("/cvs/paste", headers=headers, json={
        "text": text, "original_filename": "cv.txt", "consent_to_process": True})
    assert response.status_code == 201


def test_candidate_adds_edits_and_deletes_entries(client, db_session):
    occupations = add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    body = {"title": "Backend Developer", "start_month": "2019-03", "end_month": "2021-02",
            "occupation_concept_id": str(occupations["software developer"].id)}
    created = client.post("/candidates/me/work-entries", headers=headers, json=body)
    assert created.status_code == 201
    entry = created.json()
    assert entry["months"] == 24 and entry["source"] == "manual"
    assert entry["occupation"] == {"concept_id": str(occupations["software developer"].id),
                                   "label": "software developer", "isco_code": "2512",
                                   "isco_unit_group": "Software developers"}
    assert "employer" not in entry

    present = client.post("/candidates/me/work-entries", headers=headers, json={
        "title": "Data person", "start_month": "2021-03", "end_month": None}).json()
    assert present["end_month"] is None and present["occupation"] is None

    updated = client.put(f"/candidates/me/work-entries/{entry['id']}", headers=headers,
                         json={**body, "title": "Software Engineer", "occupation_concept_id": None})
    assert updated.status_code == 200 and updated.json()["title"] == "Software Engineer"
    listed = client.get("/candidates/me/work-entries", headers=headers).json()
    assert [item["title"] for item in listed] == ["Data person", "Software Engineer"]  # newest first

    assert client.delete(f"/candidates/me/work-entries/{entry['id']}", headers=headers).status_code == 204
    assert len(client.get("/candidates/me/work-entries", headers=headers).json()) == 1


def test_validation_and_ownership(client, db_session):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    other = register(client, "other@example.com")
    post = lambda body, h=headers: client.post("/candidates/me/work-entries", headers=h, json=body)  # noqa: E731
    assert post({"title": "x", "start_month": "2020-05", "end_month": "2020-04"}).status_code == 422
    assert post({"title": "x", "start_month": "2020-13"}).status_code == 422
    assert post({"title": "  ", "start_month": "2020-01"}).status_code == 422
    assert post({"title": "x", "start_month": "2099-01"}).status_code == 422  # future
    # Only active ESCO occupations can be chosen.
    assert post({"title": "x", "start_month": "2020-01",
                 "occupation_concept_id": "00000000-0000-0000-0000-000000000001"}).status_code == 422
    mine = post({"title": "mine", "start_month": "2020-01"}).json()
    assert client.put(f"/candidates/me/work-entries/{mine['id']}", headers=other,
                      json={"title": "x", "start_month": "2020-01"}).status_code == 404
    assert client.delete(f"/candidates/me/work-entries/{mine['id']}", headers=other).status_code == 404


def test_staff_cannot_use_work_entries(client, db_session):
    staff = manager(client, db_session)
    assert client.get("/candidates/me/work-entries", headers=staff).status_code == 403


def test_detected_entries_prefill_from_cv_dates_and_skip_stored_ones(client, db_session):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    _paste_cv(client, headers, "Work Experience\nSoftware Engineer, Example GmbH\nJan 2019 - Mar 2021\n"
                               "Data Analyst | 2016 - 2018\n\nSkills\nPython")
    detected = client.get("/candidates/me/work-entries/detected", headers=headers).json()
    assert {(d["start_month"], d["end_month"], d["month_precision"]) for d in detected} == {
        ("2019-01", "2021-03", True), ("2016-01", "2018-12", False)}
    assert {d["title"] for d in detected} == {"Software Engineer", "Data Analyst"}
    assert all(d["title_choices"] == [] for d in detected)
    assert db_session.scalar(select(func.count()).select_from(CandidateWorkEntry)) == 0  # nothing stored
    client.post("/candidates/me/work-entries", headers=headers, json={
        "title": "Software Engineer", "start_month": "2019-01", "end_month": "2021-03", "source": "cv_detected"})
    detected = client.get("/candidates/me/work-entries/detected", headers=headers).json()
    assert [d["start_month"] for d in detected] == ["2016-01"]


def test_detection_rules():
    today = date(2026, 11, 21)
    found = detect_entries("Engineer\n03/2018 – Present\nIntern at X, 2017-2017\nBorn 1990\n2030 - 2031", today)
    assert [(e.title, e.start_month, e.end_month, e.month_precision) for e in found] == [
        ("Engineer", date(2018, 3, 1), None, True),
        ("Intern", date(2017, 1, 1), date(2017, 12, 1), False)]


def test_account_deletion_removes_work_entries(client, db_session):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    client.post("/candidates/me/work-entries", headers=headers, json={"title": "x", "start_month": "2020-01"})
    assert client.post("/auth/delete-account", headers=headers,
                       json={"password": "correct-horse-password"}).status_code == 204
    assert db_session.scalar(select(func.count()).select_from(CandidateWorkEntry)) == 0


def test_detected_entry_asks_instead_of_offering_the_company(client, db_session):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    _paste_cv(client, headers, "Work Experience\nExample GmbH | Northwind | 2016 - 2018\n\nSkills\nPython")
    detected = client.get("/candidates/me/work-entries/detected", headers=headers).json()
    assert [(d["title"], d["title_choices"]) for d in detected] == [("", ["Northwind"])]

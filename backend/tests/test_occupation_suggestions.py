"""Occupation choice (D060): top-5 ESCO occupation suggestions with title clean-up; job-title linking."""
from app.taxonomy.occupations import clean_title, occupation_catalog
from tests.esco_occupations import add_esco_occupations
from tests.test_recommendations import register


def test_clean_title():
    assert clean_title("Senior Software Engineer (m/w/d)") == "Software Engineer"
    assert clean_title("Backend Developer - Remote | Berlin") == "Backend Developer"
    assert clean_title("Junior Data Scientist, Payments") == "Data Scientist"
    assert clean_title("Werkstudent Sales Manager [Full-time]") == "Sales Manager"


def test_suggestions_rank_cleaned_titles_and_return_isco(client, db_session):
    occupations = add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    url = "/candidates/me/work-entries/occupation-suggestions"
    body = client.get(url, params={"title": "Senior Software Engineer (m/w/d)"}, headers=headers).json()
    assert body[0]["label"] == "software developer" and body[0]["isco_code"] == "2512"
    assert body[0]["concept_id"] == str(occupations["software developer"].id) and body[0]["confidence"] == 0.98
    assert len(body) <= 5
    devops = client.get(url, params={"title": "DevOps Engineer"}, headers=headers).json()[0]
    assert devops["label"] == "cloud devops engineer" and devops["isco_code"] == "2512"  # via parent occupation
    assert client.get(url, params={"title": "   "}, headers=headers).json() == []
    assert client.get(url, params={"title": "zzzz qqqq"}, headers=headers).json() == []


def test_chosen_suggestion_is_stored_with_its_isco_group(client, db_session):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    suggestion = client.get("/candidates/me/work-entries/occupation-suggestions", params={"title": "DBA"},
                            headers=headers).json()[0]
    entry = client.post("/candidates/me/work-entries", headers=headers, json={
        "title": "DBA", "start_month": "2020-01", "occupation_concept_id": suggestion["concept_id"]}).json()
    assert entry["occupation"]["label"] == "database administrator" and entry["occupation"]["isco_code"] == "2521"


def test_job_title_link_uses_the_auto_approval_rule(db_session):
    add_esco_occupations(db_session)
    catalog = occupation_catalog(db_session)
    link = catalog.link_job_title("Senior Software Engineer (f/m/x)")
    assert link.automatic and link.match.label == "software developer"
    assert catalog.link_job_title("Software Developr").match is None  # fuzzy only: not determined
    assert catalog.link_job_title("Office Coordinator").match is None

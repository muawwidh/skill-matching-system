"""Job card fixes: coverage over mentioned skills when none is marked required, duplicate postings."""
from types import SimpleNamespace
from uuid import UUID

from app.matching.duplicates import collapse_duplicates, description_similarity
from tests.test_recommendations import candidate_with_skills, manager

BODY = ("We build payment software for European merchants. You will design APIs, review code and mentor "
        "engineers in a distributed team. We value ownership, clear writing and steady delivery. ") * 4


def _job(client, staff, title, description, location="", company="Acme"):
    response = client.post("/jobs", headers=staff, json={
        "title": title, "company": company, "location": location, "employment_type": "", "description": description})
    assert response.status_code == 201
    return response.json()["id"]


def _posting(title, company, location, text):
    return SimpleNamespace(title=title, company=company, location=location, cleaned_description=text, description=text)


def test_similarity_and_grouping_keep_order_and_list_locations():
    pay = " The salary range for this position in Spain is 60,000 to 80,000 EUR."
    a = _posting("Senior Engineer", "Acme", "London", BODY)
    b = _posting("senior engineer ", "ACME", "Madrid", BODY + pay)
    c = _posting("Senior Engineer", "Acme", "Paris", "A completely different role in sales operations. " * 20)
    d = _posting("Staff Engineer", "Acme", "Berlin", BODY)
    e = _posting("Senior Engineer", "Acme", "london", BODY)
    assert description_similarity(a.cleaned_description, b.cleaned_description) >= 0.9
    groups = collapse_duplicates([a, c, d, b, e])
    assert [g.job for g in groups] == [a, c, d]  # best-ranked posting kept in place; others keep their order
    assert groups[0].duplicates == [b, e] and groups[0].locations == ["London", "Madrid"]
    assert groups[1].duplicates == [] and groups[1].locations == ["Paris"]


def test_candidate_list_shows_one_card_per_posting(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    london = _job(client, staff, "Backend Engineer", "Required skills\nPython\n\n" + BODY, "London")
    other = _job(client, staff, "Data Analyst", "Required skills\nSQL\n\n" + BODY, "Vilnius")
    madrid = _job(client, staff, "Backend Engineer", "Required skills\nPython\n\n" + BODY + " Madrid office.", "Madrid")
    headers = candidate_with_skills(client)
    fake_retrieval["order"] = [UUID(london), UUID(other), UUID(madrid)]

    body = client.get("/matches/recommendations", headers=headers).json()
    assert [(item["rank"], item["job_id"]) for item in body["results"]] == [(1, london), (2, other)]
    assert body["total"] == 2 and body["collapsed_duplicates"] == 1
    assert body["results"][0]["locations"] == ["London", "Madrid"]
    assert body["results"][0]["duplicate_job_ids"] == [madrid]
    assert body["results"][1]["locations"] == ["Vilnius"] and body["results"][1]["duplicate_job_ids"] == []
    # The duplicate stays in the database and can still be opened.
    assert client.get(f"/matches/jobs/{madrid}", headers=headers).status_code == 200


def test_coverage_basis_required_mentioned_or_none(client, db_session, fake_retrieval):
    staff = manager(client, db_session)
    required = _job(client, staff, "Required", "Required skills\nPython\n")
    mentioned = _job(client, staff, "Mentioned", "About the role\nYou will use Python and Docker every day.\n")
    nothing = _job(client, staff, "Nothing", "About the role\nYou will greet visitors.\n")
    for job_id in (required, mentioned):
        for skill in client.get(f"/jobs/{job_id}/extracted-skills", headers=staff).json():
            skill["review_status"] = "approved"
            client.put(f"/jobs/{job_id}/extracted-skills/{skill['id']}", headers=staff, json=skill)
    headers = candidate_with_skills(client)
    fake_retrieval["order"] = [UUID(required), UUID(mentioned), UUID(nothing)]

    items = {item["job"]["title"]: item for item in client.get("/matches/recommendations", headers=headers).json()["results"]}
    assert items["Required"]["coverage_basis"] == "required"
    mentioned_item = items["Mentioned"]
    assert mentioned_item["coverage_basis"] == "mentioned"
    assert not mentioned_item["matched_required"] and not mentioned_item["missing_required"]
    assert {e["label"] for e in mentioned_item["matched_preferred"]} == {"python"}
    assert {e["label"] for e in mentioned_item["missing_preferred"]} == {"docker"}
    assert items["Nothing"]["coverage_basis"] == "none"
    # Ranking unchanged: retrieval order.
    assert [items[t]["rank"] for t in ("Required", "Mentioned", "Nothing")] == [1, 2, 3]
    assert client.get(f"/matches/jobs/{mentioned}", headers=headers).json()["coverage_basis"] == "mentioned"

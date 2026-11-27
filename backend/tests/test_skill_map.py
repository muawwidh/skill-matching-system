"""Skill map data (display only): ESCO areas on coverage entries and profile skills, and `not_needed`."""
from sqlalchemy import select

from app.db.models import TaxonomyConcept, TaxonomyRelationship
from app.repositories.document_repository import DocumentRepository
from app.services.matching_service import SkillItem, _JobGroup, _not_needed
from tests.test_partial_coverage import _broader, _concept, _sample_esco


def _group(db, version, code, label):
    concept = _concept(db, version, label, "skill_group")
    concept.metadata_json = {"source": {"code": code}}
    return concept


def test_area_is_the_group_just_below_the_top(db_session):
    version, concepts = _sample_esco(db_session)
    python, sql = concepts["Python (computer programming)"], concepts["SQL"]
    knowledge = _group(db_session, version, "K", "knowledge")
    ict = _group(db_session, version, "06", "information and communication technologies (icts)")
    narrow = _group(db_session, version, "061", "information and communication technologies")
    detailed = _group(db_session, version, "0613", "software and applications development and analysis")
    programming = _concept(db_session, version, "computer programming", "skill")
    _broader(db_session, version, ict, knowledge)
    _broader(db_session, version, narrow, ict)
    _broader(db_session, version, detailed, narrow)
    _broader(db_session, version, programming, detailed)
    _broader(db_session, version, python, programming)  # python -> skill -> 0613 -> 061 -> 06 -> K
    top_only = _group(db_session, version, "T", "transversal skills and competences")
    _broader(db_session, version, sql, top_only)  # only a top-level group: used as the fallback
    db_session.commit()

    repo = DocumentRepository(db_session)
    assert repo.esco_areas({python.id, sql.id, ict.id}) == {
        python.id: ("06", "information and communication technologies (icts)"),
        sql.id: ("T", "transversal skills and competences"),
        ict.id: ("K", "knowledge"),
    }
    assert repo.esco_areas(set()) == {}
    version.status = "inactive"
    db_session.commit()
    assert repo.esco_areas({python.id}) == {}


def test_not_needed_lists_profile_skills_the_job_does_not_ask_for():
    from uuid import uuid4

    linked, other = uuid4(), uuid4()
    candidate = [
        SkillItem("python", "skill", linked, "Python"),
        SkillItem("sql", "skill"),
        SkillItem("excel", "tool", other, "Microsoft Excel"),
        SkillItem("excel", "tool", other, "Microsoft Excel"),  # same concept once
        SkillItem("english", "language"),
        SkillItem("bachelor", "qualification"),  # not a skill
    ]
    groups = [_JobGroup("Python", linked, {"python"}, True), _JobGroup("sql", None, {"sql"}, False)]
    assert [item.concept_label or item.name for item in _not_needed(candidate, groups)] == ["english", "Microsoft Excel"]


def test_job_detail_returns_not_needed_and_areas(client, db_session, fake_retrieval):
    from uuid import UUID

    from tests.test_recommendations import candidate_with_skills, manager

    staff = manager(client, db_session)
    job = client.post("/jobs", headers=staff, json={"title": "Ops", "company": "", "location": "",
                                                    "employment_type": "", "description": "Required skills\nDocker\n"}).json()
    for skill in client.get(f"/jobs/{job['id']}/extracted-skills", headers=staff).json():
        skill["review_status"] = "approved"
        client.put(f"/jobs/{job['id']}/extracted-skills/{skill['id']}", headers=staff, json=skill)
    headers = candidate_with_skills(client)
    fake_retrieval["order"] = [UUID(job["id"])]
    detail = client.get(f"/matches/jobs/{job['id']}", headers=headers).json()
    assert detail["missing_required"][0]["esco_area"] is None  # unlinked
    assert detail["not_needed"] and all(set(entry) == {"label", "esco_area"} for entry in detail["not_needed"])
    # The list does not carry the profile's skills.
    listed = client.get("/matches/recommendations", headers=headers).json()["results"][0]
    assert "not_needed" not in listed


def test_manual_skills_carry_an_area_field(client):
    from tests.test_recommendations import register

    headers = register(client, "hand@example.com")
    assert client.post("/candidates/me/manual-skills", headers=headers, json={"label": "Kubernetes"}).status_code == 201
    (skill,) = client.get("/candidates/me/manual-skills", headers=headers).json()
    assert skill["raw_text"] == "Kubernetes" and skill["esco_area"] is None  # no taxonomy loaded: no area

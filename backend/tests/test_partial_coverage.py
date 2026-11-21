"""Related job skills ("Related skill in your profile") via a shared ESCO broader skill/knowledge concept (D050)."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db.models import Role, TaxonomyConcept, TaxonomyRelationship, TaxonomySource, TaxonomyVersion, User
from app.repositories.document_repository import DocumentRepository
from app.services.matching_service import SkillItem, build_explanation, compute_coverage
from app.services.taxonomy_service import TaxonomyService

PY, SQL, DOCKER, GIT, PROG, GROUP = (uuid4() for _ in range(6))


def item(name, concept=None, label=None, requirement="required"):
    return SkillItem(name=name, skill_type="skill", concept_id=concept, concept_label=label, requirement=requirement)


def test_shared_broader_concept_is_partial_not_matched():
    candidate = [item("python", PY, "Python"), item("git", None, None)]
    job = [item("sql", SQL, "SQL"), item("docker", DOCKER, "Docker", "preferred"),
           item("python", PY, "Python"), item("kotlin", None, None)]
    broader = {PY: {PROG: "computer programming"}, SQL: {PROG: "computer programming"}}

    result = compute_coverage(candidate, job, broader)
    assert result.matched_required == [{"label": "Python", "matched_via": "taxonomy_concept"}]
    assert result.partial_required == [
        {"label": "SQL", "broader_concept": "computer programming", "candidate_skill": "Python"}]
    assert result.missing_required == [{"label": "kotlin", "checked_via": "skill_name"}]
    assert result.missing_preferred == [{"label": "Docker", "checked_via": "taxonomy_concept"}]
    assert result.required_total == 3 and result.preferred_total == 1
    text = build_explanation(result)
    assert "Required skills: 1 of 3 matched (Python); related skill in your profile: SQL; missing: kotlin." in text
    assert "SQL: not in your CV, but related: you have Python (same ESCO area: computer programming)." in text

    # Without the broader map (offline comparison, D043) nothing is partial.
    plain = compute_coverage(candidate, job)
    assert plain.partial_required == [] and {e["label"] for e in plain.missing_required} == {"SQL", "kotlin"}


def test_unlinked_or_name_matched_skills_are_never_partial():
    broader = {PY: {PROG: "computer programming"}, SQL: {PROG: "computer programming"}}
    # An unlinked candidate skill has no concept, so no broader evidence.
    assert compute_coverage([item("python")], [item("sql", SQL, "SQL")], broader).partial_required == []
    # A name match wins over a partial match.
    result = compute_coverage([item("python", PY, "Python"), item("sql")], [item("sql", SQL, "SQL")], broader)
    assert result.matched_required == [{"label": "SQL", "matched_via": "skill_name"}]
    assert result.partial_required == []


def _concept(db, version, label, concept_type):
    concept = TaxonomyConcept(taxonomy_version_id=version.id, external_id=f"urn:test:{label}",
                              preferred_label=label, normalized_label=label.lower(), concept_type=concept_type)
    db.add(concept)
    db.flush()
    return concept


def _broader(db, version, child, parent):
    db.add(TaxonomyRelationship(taxonomy_version_id=version.id, source_concept_id=child.id,
                                target_concept_id=parent.id, relationship_type="broader"))


def _sample_esco(db):
    TaxonomyService(db).import_bundled_sample()
    version = db.scalar(select(TaxonomyVersion).join(TaxonomySource).where(TaxonomySource.code == "ESCO"))
    by_label = {c.preferred_label: c for c in db.scalars(
        select(TaxonomyConcept).where(TaxonomyConcept.taxonomy_version_id == version.id))}
    return version, by_label


def test_repository_keeps_only_active_esco_skill_or_knowledge_parents(db_session):
    version, concepts = _sample_esco(db_session)
    python, sql = concepts["Python (computer programming)"], concepts["SQL"]
    programming = _concept(db_session, version, "computer programming", "skill")
    databases = _concept(db_session, version, "databases", "knowledge")
    group = _concept(db_session, version, "software and applications development", "skill_group")
    _broader(db_session, version, python, programming)
    _broader(db_session, version, sql, databases)
    _broader(db_session, version, python, group)
    db_session.commit()

    repo = DocumentRepository(db_session)
    assert repo.specific_esco_broader_concepts({python.id, sql.id}) == {
        python.id: {programming.id: "computer programming"}, sql.id: {databases.id: "databases"}}
    assert repo.specific_esco_broader_concepts(set()) == {}
    version.status = "inactive"
    db_session.commit()
    assert repo.specific_esco_broader_concepts({python.id, sql.id}) == {}


def test_recommendations_show_partial_coverage(client, db_session, fake_retrieval):
    version, concepts = _sample_esco(db_session)
    programming = _concept(db_session, version, "computer programming", "skill")
    group = _concept(db_session, version, "software and applications development", "skill_group")
    _broader(db_session, version, concepts["Python (computer programming)"], programming)
    _broader(db_session, version, concepts["SQL"], programming)
    _broader(db_session, version, concepts["Python (computer programming)"], group)
    _broader(db_session, version, concepts["containerisation software"], group)
    db_session.commit()

    staff = client.post("/auth/register", json={
        "email": "manager@example.com", "full_name": "Synthetic", "password": "correct-horse-password"})
    staff_headers = {"Authorization": f"Bearer {staff.json()['access_token']}"}
    user = db_session.scalar(select(User).where(User.email == "manager@example.com"))
    user.roles.append(Role(name="admin", description=""))
    db_session.commit()
    job = client.post("/jobs", headers=staff_headers, json={
        "title": "Data role", "company": "", "location": "", "employment_type": "",
        "description": "Required skills\nSQL\nDocker"}).json()
    for skill in client.get(f"/jobs/{job['id']}/extracted-skills", headers=staff_headers).json():
        skill["review_status"] = "approved"
        assert client.put(f"/jobs/{job['id']}/extracted-skills/{skill['id']}", headers=staff_headers,
                          json=skill).status_code == 200

    candidate = client.post("/auth/register", json={
        "email": "candidate@example.com", "full_name": "Synthetic", "password": "correct-horse-password"})
    headers = {"Authorization": f"Bearer {candidate.json()['access_token']}"}
    cv = client.post("/cvs/paste", headers=headers, json={
        "text": "Skills\nPython", "original_filename": "cv.txt", "consent_to_process": True}).json()
    skills = client.get(f"/cvs/{cv['id']}/extracted-skills", headers=headers).json()
    for skill in skills:
        skill["review_status"] = "approved"
    assert client.put(f"/cvs/{cv['id']}/extracted-skills", headers=headers, json={"skills": skills}).status_code == 200

    fake_retrieval["indexed_profile"] = True
    body = client.get("/matches/recommendations", headers=headers).json()
    (result,) = body["results"]
    assert result["matched_required"] == []
    assert result["partial_required"] == [{"label": "SQL", "broader_concept": "computer programming",
                                           "candidate_skill": "Python (computer programming)",
                                           "reviewed": True}]
    # Docker shares only a broad skill group with Python: still missing.
    assert result["missing_required"] == [{"label": "containerisation software", "checked_via": "taxonomy_concept", "reviewed": True}]
    assert ("SQL: not in your CV, but related: you have Python (computer programming) "
            "(same ESCO area: computer programming).") in result["explanation"]
    assert client.get(f"/matches/jobs/{job['id']}", headers=headers).json()["partial_required"] == \
        result["partial_required"]

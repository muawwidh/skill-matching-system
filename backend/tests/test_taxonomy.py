from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.db.models import ApprovedTaxonomyLink, Role, User
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.taxonomy.linker import TaxonomyLinker


def register(client: TestClient, email: str = "researcher@example.com") -> str:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "full_name": "Taxonomy Researcher",
            "password": "correct-horse-password",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def grant_researcher(db_session: Session, email: str = "researcher@example.com") -> None:
    user = db_session.scalar(select(User).where(User.email == email))
    role = Role(name="researcher", description="Taxonomy research access")
    db_session.add(role)
    db_session.flush()
    user.roles.append(role)
    db_session.commit()


def test_taxonomy_import_requires_administrator_role(
    client: TestClient,
) -> None:
    token = register(client, "candidate-taxonomy@example.com")
    response = client.post(
        "/taxonomy/import/sample",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_sample_import_search_mapping_and_automatic_linking(
    client: TestClient,
    db_session: Session,
) -> None:
    token = register(client)
    grant_researcher(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    import_response = client.post("/taxonomy/import/sample", headers=headers)
    assert import_response.status_code == 200
    results = import_response.json()
    assert results[0]["source_code"] == "ESCO"
    assert results[0]["concepts_imported"] == 8
    assert results[1]["source_code"] == "ONET"
    assert results[1]["occupations_imported"] == 2
    assert results[2]["mappings_imported"] == 2

    search_response = client.get("/taxonomy/search?q=Python", headers=headers)
    assert search_response.status_code == 200
    python_concept = search_response.json()[0]
    assert python_concept["source_code"] == "ESCO"
    assert "Python" in python_concept["alternative_labels"]

    mappings_response = client.get("/taxonomy/mappings", headers=headers)
    assert mappings_response.status_code == 200
    assert {item["onet_code"] for item in mappings_response.json()} == {
        "15-1252.00",
        "15-2051.00",
    }

    cv_response = client.post(
        "/cvs/paste",
        headers=headers,
        json={
            "text": "SUMMARY\nBackend developer\nSKILLS\nPython, Docker, FastAPI",
            "original_filename": "taxonomy-cv.txt",
            "consent_to_process": True,
        },
    )
    assert cv_response.status_code == 201
    approved_count = db_session.scalar(select(func.count()).select_from(ApprovedTaxonomyLink))
    assert approved_count >= 3


def test_fuzzy_linking_returns_review_candidate(client: TestClient, db_session: Session) -> None:
    token = register(client)
    grant_researcher(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/taxonomy/import/sample", headers=headers).status_code == 200

    concepts = []
    search_response = client.get("/taxonomy/search?q=Python", headers=headers)
    assert search_response.status_code == 200
    concept_id = search_response.json()[0]["id"]
    concepts.append(TaxonomyRepository(db_session).get_concept(UUID(concept_id)))
    ranked = TaxonomyLinker().rank("Pythn", concepts)
    assert ranked
    assert ranked[0].method == "fuzzy"
    assert 0.70 <= ranked[0].confidence < 0.95


def test_researcher_can_approve_pending_taxonomy_link(
    client: TestClient,
    db_session: Session,
) -> None:
    token = register(client)
    grant_researcher(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/taxonomy/import/sample", headers=headers).status_code == 200

    concept = TaxonomyRepository(db_session).active_concepts()[0]
    candidate = TaxonomyRepository(db_session).add_link_candidate(
        term_source="candidate",
        extracted_term_id=uuid4(),
        raw_text="Pythn",
        normalized_text="pythn",
        concept_id=concept.id,
        match_method="fuzzy",
        confidence_score=0.82,
        rank=1,
        review_status="pending",
    )
    db_session.commit()

    review_response = client.get("/admin/mappings/review", headers=headers)
    assert review_response.status_code == 200
    assert review_response.json()[0]["id"] == str(candidate.id)

    approve_response = client.put(
        f"/taxonomy/link/{candidate.id}/approve",
        headers=headers,
        json={"status": "approved"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["review_status"] == "approved"
    assert db_session.scalar(select(func.count()).select_from(ApprovedTaxonomyLink)) == 1

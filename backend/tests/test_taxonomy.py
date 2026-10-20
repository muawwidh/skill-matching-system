from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.db.models import ApprovedTaxonomyLink, Role, TaxonomyConcept, TaxonomyLabel, User
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.taxonomy.linker import TaxonomyLinker
from app.taxonomy.normalization import normalize_taxonomy_text


def concept_for_ranking(preferred: str, alternatives: tuple[str, ...] = (), version_id: UUID | None = None) -> TaxonomyConcept:
    concept = TaxonomyConcept(
        id=uuid4(), taxonomy_version_id=version_id or uuid4(), external_id=str(uuid4()),
        preferred_label=preferred, normalized_label=normalize_taxonomy_text(preferred),
        concept_type="skill", language="en",
    )
    concept.labels = [TaxonomyLabel(label=label, normalized_label=normalize_taxonomy_text(label),
                                    label_type="alternative", language="en") for label in alternatives]
    return concept


@pytest.mark.parametrize(
    ("preferred", "alternatives", "query", "method", "confidence"),
    [
        ("Unique preferred", (), "Unique preferred", "exact_preferred", 1.0),
        ("Different preferred", ("Unique alternative",), "Unique alternative", "exact_alternative", 0.98),
    ],
)
def test_unique_top_concept_preserves_exact_match_precedence(preferred, alternatives, query, method, confidence):
    ranked, unique = TaxonomyLinker().rank_with_top_uniqueness(query, [concept_for_ranking(preferred, alternatives)])
    assert unique is True
    assert [(item.method, item.confidence) for item in ranked] == [(method, confidence)]


@pytest.mark.parametrize("match_kind", ["preferred", "alternative"])
def test_distinct_equal_confidence_concepts_remain_ambiguous_after_limit_and_reversal(match_kind):
    releases = (uuid4(), uuid4())
    if match_kind == "preferred":
        concepts = [concept_for_ranking("Shared term", version_id=version) for version in releases]
        expected = 1.0
    else:
        concepts = [concept_for_ranking(f"Different {index}", ("Shared term",), version) for index, version in enumerate(releases)]
        expected = 0.98
    linker = TaxonomyLinker(max_candidates=1)
    first, first_unique = linker.rank_with_top_uniqueness("Shared term", concepts)
    reversed_rank, reversed_unique = linker.rank_with_top_uniqueness("Shared term", list(reversed(concepts)))
    assert len(first) == len(reversed_rank) == 1
    assert first_unique is reversed_unique is False
    assert first[0].concept.id == reversed_rank[0].concept.id
    assert first[0].confidence == expected


def test_preferred_match_beats_alternative_and_duplicate_labels_do_not_create_ambiguity():
    preferred = concept_for_ranking("Shared term")
    alternative = concept_for_ranking("Different term", ("Shared term", "Shared term"))
    ranked, unique = TaxonomyLinker().rank_with_top_uniqueness("Shared term", [alternative, preferred])
    assert unique is True
    assert [(item.concept.id, item.method, item.confidence) for item in ranked] == [
        (preferred.id, "exact_preferred", 1.0), (alternative.id, "exact_alternative", 0.98)
    ]
    duplicated, same_concept_unique = TaxonomyLinker().rank_with_top_uniqueness(
        "Shared term", [alternative, alternative]
    )
    assert same_concept_unique is True
    assert [(item.concept.id, item.method, item.confidence) for item in duplicated] == [
        (alternative.id, "exact_alternative", 0.98)
    ]


def test_below_auto_approval_threshold_still_ranks_for_review():
    ranked, unique = TaxonomyLinker().rank_with_top_uniqueness("Pythn", [concept_for_ranking("Python")])
    assert unique is True
    assert ranked and ranked[0].method == "fuzzy" and ranked[0].confidence < 0.95


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

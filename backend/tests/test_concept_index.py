"""ConceptIndex ranks exactly like the reference TaxonomyLinker; cached until the taxonomy changes."""
import random
from uuid import uuid4

from sqlalchemy import select

from app.db.models import TaxonomyConcept, TaxonomyLabel
from app.repositories.taxonomy_repository import TaxonomyRepository
from app.taxonomy import concept_index
from app.taxonomy.concept_index import ConceptIndex, IndexedConcept, active_concept_index
from app.taxonomy.linker import TaxonomyLinker
from tests.test_taxonomy import concept_for_ranking

WORDS = ["python", "data", "analysis", "project", "management", "sql", "cloud", "computing", "customer",
         "service", "java", "script", "machine", "learning", "docker", "excel", "sales", "support"]


def _index_from(concepts) -> ConceptIndex:
    return ConceptIndex([IndexedConcept(c.id, c.taxonomy_version_id, c.preferred_label, c.normalized_label)
                         for c in concepts],
                        {c.id: {label.normalized_label for label in c.labels} for c in concepts})


def _key(ranked, unique):
    return [(r.concept.id, r.method, r.confidence) for r in ranked], unique


def test_index_matches_reference_linker_on_random_taxonomy():
    rng = random.Random(20261121)
    version = uuid4()
    concepts = []
    for n in range(300):
        preferred = " ".join(rng.sample(WORDS, rng.randint(1, 3)))
        alternatives = tuple(" ".join(rng.sample(WORDS, rng.randint(1, 3))) for _ in range(rng.randint(0, 3)))
        # Some duplicates across concepts and a second version, to exercise ties and ordering.
        concepts.append(concept_for_ranking(preferred, alternatives, version if n % 7 else uuid4()))
    reference, index = TaxonomyLinker(), _index_from(concepts)
    queries = [c.preferred_label for c in concepts[:60]] + [rng.choice(WORDS) + "s" for _ in range(40)]
    queries += [" ".join(rng.sample(WORDS, 2)) for _ in range(60)] + ["Pythn", "", "!!!", "SQL "]
    for query in queries:
        assert _key(*index.rank_with_top_uniqueness(query)) == _key(*reference.rank_with_top_uniqueness(query, concepts)), query


def test_exact_and_fuzzy_methods_and_cache():
    concepts = [concept_for_ranking("Python (computer programming)", ("Python",)),
                concept_for_ranking("Pythonic style"), concept_for_ranking("SQL")]
    index = _index_from(concepts)
    ranked, unique = index.rank_with_top_uniqueness("python")
    assert (ranked[0].method, ranked[0].confidence, unique) == ("exact_alternative", 0.98, True)
    assert index.rank_with_top_uniqueness("SQL")[0][0].method == "exact_preferred"
    assert index.rank_with_top_uniqueness("Pythn")[0][0].method == "fuzzy"
    assert "python" in index._cache
    # A cached result is returned as a copy: callers cannot change it.
    index.rank_with_top_uniqueness("python")[0].clear()
    assert index.rank_with_top_uniqueness("python")[0]


def test_active_index_is_reused_until_the_taxonomy_changes(client, db_session):
    concept_index.clear_concept_index_cache()
    from tests.test_taxonomy import grant_researcher, register
    headers = {"Authorization": f"Bearer {register(client)}"}
    grant_researcher(db_session)
    assert client.post("/taxonomy/import/sample", headers=headers).status_code == 200
    first = active_concept_index(db_session)
    assert active_concept_index(db_session) is first
    assert len(first) == len(TaxonomyRepository(db_session).active_concepts())
    concept = db_session.scalar(select(TaxonomyConcept).order_by(TaxonomyConcept.id))
    db_session.add(TaxonomyLabel(concept_id=concept.id, label="Snake language", normalized_label="snake language",
                                 label_type="alternative", language="en"))
    db_session.commit()
    second = active_concept_index(db_session)
    assert second is not first
    assert second.rank_with_top_uniqueness("snake language")[0][0].concept.id == concept.id

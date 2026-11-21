"""Embedding neighbours in work-entry occupation suggestions (D060): string-based first, max 5, no duplicates."""
import hashlib
import math

import pytest
from sqlalchemy import func, select

from app.db.models import OccupationLabelEmbedding
from app.retrieval.representation import MODEL_ID, MODEL_REVISION
from app.taxonomy import occupation_embeddings
from app.taxonomy.occupation_embeddings import embed_occupation_labels
from tests.esco_occupations import add_esco_occupations
from tests.test_recommendations import register

URL = "/candidates/me/work-entries/occupation-suggestions"
SYNONYMS = {"coder": "software", "code": "software", "databases": "database", "selling": "sales"}


class BagOfWordsEmbedder:
    """Deterministic stand-in for E5: hashed bag of words (prefix dropped, a few synonyms), normalized."""

    def __init__(self):
        self.calls = []

    def encode(self, text):
        self.calls.append(text)
        vector = [0.0] * 384
        for word in text.split(":", 1)[-1].lower().split():
            word = SYNONYMS.get(word, word)
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 384] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


@pytest.fixture
def embedder(monkeypatch):
    fake = BagOfWordsEmbedder()
    monkeypatch.setattr(occupation_embeddings, "query_embedder", lambda: fake)
    return fake


def test_without_stored_embeddings_suggestions_stay_string_based(client, db_session, embedder):
    add_esco_occupations(db_session)
    headers = register(client, "candidate@example.com")
    body = client.get(URL, params={"title": "Senior Software Engineer (m/w/d)"}, headers=headers).json()
    assert body and {item["method"] for item in body} == {"label"}
    assert client.get(URL, params={"title": "code writer"}, headers=headers).json() == []
    assert embedder.calls == []  # no label vectors: the title is not embedded


def test_label_embeddings_are_computed_once_with_model_identity(db_session):
    add_esco_occupations(db_session)
    fake = BagOfWordsEmbedder()
    first = embed_occupation_labels(db_session, fake)
    assert first["embedded"] == first["labels"] > 5 and first["already_stored"] == 0  # preferred + alternative labels
    assert all(text.startswith("passage: ") for text in fake.calls)
    second = embed_occupation_labels(db_session, fake)
    assert second["embedded"] == 0 and second["already_stored"] == first["labels"]
    rows = db_session.scalar(select(func.count()).select_from(OccupationLabelEmbedding).where(
        OccupationLabelEmbedding.model_id == MODEL_ID, OccupationLabelEmbedding.model_revision == MODEL_REVISION))
    assert rows == first["labels"]


def test_embedding_neighbours_follow_string_suggestions_deduplicated_max_five(client, db_session, embedder):
    occupations = add_esco_occupations(db_session)
    embed_occupation_labels(db_session, BagOfWordsEmbedder())
    headers = register(client, "candidate@example.com")

    body = client.get(URL, params={"title": "DevOps Engineer"}, headers=headers).json()
    methods = [item["method"] for item in body]
    assert len(body) == 5 and len({item["concept_id"] for item in body}) == 5
    assert methods == sorted(methods, key=lambda m: m != "label")  # string-based first
    assert methods[0] == "label" and body[0]["label"] == "cloud devops engineer"
    assert "embedding" in methods
    assert embedder.calls[-1] == "query: DevOps Engineer"

    only_meaning = client.get(URL, params={"title": "Senior code writer"}, headers=headers).json()
    assert only_meaning[0]["method"] == "embedding"
    assert only_meaning[0]["concept_id"] == str(occupations["software developer"].id)
    assert embedder.calls[-1] == "query: code writer"  # cleaned title
    assert len(only_meaning) == 5

    calls = len(embedder.calls)
    assert client.get(URL, params={"title": "   "}, headers=headers).json() == []
    assert len(embedder.calls) == calls  # blank titles are not embedded


def test_missing_model_falls_back_to_string_suggestions(client, db_session, monkeypatch):
    add_esco_occupations(db_session)
    embed_occupation_labels(db_session, BagOfWordsEmbedder())

    def unavailable():
        raise RuntimeError("Pinned E5 model is unavailable locally.")

    monkeypatch.setattr(occupation_embeddings, "query_embedder", unavailable)
    headers = register(client, "candidate@example.com")
    body = client.get(URL, params={"title": "Software Engineer"}, headers=headers).json()
    assert body and {item["method"] for item in body} == {"label"}

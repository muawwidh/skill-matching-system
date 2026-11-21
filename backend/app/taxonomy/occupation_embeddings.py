"""Embedding nearest neighbours for work-entry occupation suggestions (DECISIONS.md D060).

Only the candidate's work-entry form uses these, as extra suggestions after the
string-based ones; the candidate picks one or none. Job occupations never use
them (rejected in D060: about half the nearest occupations were wrong).

Occupation labels (ESCO preferred + alternative, active versions) are embedded
once with the pinned E5 model ("passage: " prefix) by the CLI command
`embed-occupation-labels` and stored with model id and revision. Lookups load
the stored vectors once into memory and embed the cleaned title ("query: ").
"""
from __future__ import annotations

import logging
import threading
import time
from uuid import UUID

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.retrieval.representation import MODEL_ID, MODEL_REVISION
from app.taxonomy.concept_index import _fingerprint
from app.taxonomy.normalization import normalize_taxonomy_text
from app.taxonomy.occupations import clean_title

log = logging.getLogger("uvicorn.error")
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def _active_occupation_labels(db: Session) -> list[tuple[UUID, str]]:
    from app.db.models import TaxonomyConcept, TaxonomyLabel, TaxonomySource, TaxonomyVersion

    versions = select(TaxonomyVersion.id).join(TaxonomySource, TaxonomySource.id == TaxonomyVersion.source_id).where(
        TaxonomySource.code == "ESCO", TaxonomyVersion.status == "active")
    concepts = select(TaxonomyConcept.id, TaxonomyConcept.preferred_label).where(
        TaxonomyConcept.taxonomy_version_id.in_(versions), TaxonomyConcept.concept_type == "occupation")
    pairs = {(row.id, row.preferred_label.strip()) for row in db.execute(concepts)}
    ids = select(TaxonomyConcept.id).where(TaxonomyConcept.taxonomy_version_id.in_(versions),
                                           TaxonomyConcept.concept_type == "occupation")
    for concept_id, label in db.execute(select(TaxonomyLabel.concept_id, TaxonomyLabel.label)
                                        .where(TaxonomyLabel.concept_id.in_(ids))):
        pairs.add((concept_id, label.strip()))
    return sorted((pair for pair in pairs if pair[1] and len(pair[1]) <= 512), key=lambda p: (str(p[0]), p[1]))


def _encode(embedder, texts: list[str]) -> list[list[float]]:
    model = getattr(embedder, "model", None)
    if model is not None:  # LocalE5Embedder: batch encode
        return [list(map(float, row)) for row in model.encode(texts, batch_size=256, normalize_embeddings=True,
                                                               convert_to_numpy=True)]
    return [embedder.encode(text) for text in texts]


def embed_occupation_labels(db: Session, embedder, batch_size: int = 1024) -> dict:
    """Embed every active occupation label not yet stored for the pinned model. Idempotent."""
    from app.db.models import OccupationLabelEmbedding

    started = time.perf_counter()
    labels = _active_occupation_labels(db)
    stored = set(db.execute(select(OccupationLabelEmbedding.concept_id, OccupationLabelEmbedding.label).where(
        OccupationLabelEmbedding.model_id == MODEL_ID, OccupationLabelEmbedding.model_revision == MODEL_REVISION)))
    missing = [pair for pair in labels if pair not in stored]
    for start in range(0, len(missing), batch_size):
        chunk = missing[start:start + batch_size]
        vectors = _encode(embedder, [PASSAGE_PREFIX + label for _, label in chunk])
        db.add_all(OccupationLabelEmbedding(concept_id=concept_id, label=label, embedding=vector,
                                            model_id=MODEL_ID, model_revision=MODEL_REVISION)
                   for (concept_id, label), vector in zip(chunk, vectors))
        db.flush()
    db.commit()
    clear_label_matrix()
    return {"model": MODEL_ID, "revision": MODEL_REVISION, "labels": len(labels), "embedded": len(missing),
            "already_stored": len(labels) - len(missing), "seconds": round(time.perf_counter() - started, 1)}


class LabelMatrix:
    def __init__(self, concept_ids: list[UUID], vectors: np.ndarray) -> None:
        self.concept_ids = concept_ids
        self.vectors = vectors

    def nearest(self, query: list[float], limit: int) -> list[tuple[UUID, float]]:
        """Distinct occupations by their best label's cosine similarity (vectors are normalized)."""
        if not self.concept_ids:
            return []
        sims = self.vectors @ np.asarray(query, dtype=np.float32)
        result: dict[UUID, float] = {}
        for index in np.argsort(-sims, kind="stable"):
            concept_id = self.concept_ids[int(index)]
            if concept_id not in result:
                result[concept_id] = float(sims[int(index)])
                if len(result) == limit:
                    break
        return list(result.items())


_lock = threading.Lock()
_cached: tuple[tuple, LabelMatrix] | None = None


def label_matrix(db: Session) -> LabelMatrix:
    """Stored label vectors of active occupations for the pinned model, loaded once per taxonomy/row count."""
    global _cached
    from app.db.models import OccupationLabelEmbedding, TaxonomyConcept, TaxonomySource, TaxonomyVersion

    active = select(TaxonomyConcept.id).join(TaxonomyVersion, TaxonomyVersion.id == TaxonomyConcept.taxonomy_version_id) \
        .join(TaxonomySource, TaxonomySource.id == TaxonomyVersion.source_id) \
        .where(TaxonomySource.code == "ESCO", TaxonomyVersion.status == "active", TaxonomyConcept.concept_type == "occupation")
    scope = (OccupationLabelEmbedding.model_id == MODEL_ID, OccupationLabelEmbedding.model_revision == MODEL_REVISION,
             OccupationLabelEmbedding.concept_id.in_(active))
    key = (_fingerprint(db), db.scalar(select(func.count()).select_from(OccupationLabelEmbedding).where(*scope)))
    with _lock:
        if _cached is not None and _cached[0] == key:
            return _cached[1]
        rows = list(db.execute(select(OccupationLabelEmbedding.concept_id, OccupationLabelEmbedding.embedding)
                               .where(*scope).order_by(OccupationLabelEmbedding.concept_id, OccupationLabelEmbedding.label)))
        vectors = np.asarray([list(row.embedding) for row in rows], dtype=np.float32).reshape(len(rows), -1) \
            if rows else np.zeros((0, 0), dtype=np.float32)
        matrix = LabelMatrix([row.concept_id for row in rows], vectors)
        _cached = (key, matrix)
        return matrix


def clear_label_matrix() -> None:
    global _cached
    with _lock:
        _cached = None


def query_embedder():
    """The process-wide pinned E5 embedder (shared with automatic re-embedding)."""
    from app.retrieval.auto_reindex import get_embedder

    return get_embedder()


def nearest_occupations(db: Session, title: str, limit: int) -> list[tuple[UUID, float]]:
    """Nearest occupations for a work-entry title, or [] when no label embeddings or no model."""
    cleaned = clean_title(title) or title
    if limit <= 0 or not normalize_taxonomy_text(cleaned):
        return []
    matrix = label_matrix(db)
    if not matrix.concept_ids:
        return []
    try:
        embedder = query_embedder()
        query = embedder.encode(QUERY_PREFIX + cleaned.strip())
    except Exception as exc:  # model missing: string-based suggestions only
        log.warning("Occupation embedding suggestions unavailable: %s", exc)
        return []
    return matrix.nearest(query, limit)

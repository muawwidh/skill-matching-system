"""Opt-in smoke test; never downloads model files."""
import os

import pytest
from sqlalchemy.orm import Session

from app.db.models import User
from app.retrieval.embedder import LocalE5Embedder
from app.retrieval.representation import DIMENSION
from app.services.retrieval_service import RetrievalService
from test_retrieval_postgres import pg_retrieval  # noqa: F401


def test_real_pinned_model_postgres_retrieval(pg_retrieval):
    path = os.environ.get("PHASE5_REAL_MODEL_PATH")
    if not path:
        pytest.skip("UNVERIFIED: PHASE5_REAL_MODEL_PATH is not set")
    engine, _, profile_id, job_id, user_id = pg_retrieval
    model = LocalE5Embedder(path)
    assert len(model.encode("query: Python engineer")) == DIMENSION
    with Session(engine) as db:
        service = RetrievalService(db)
        assert service.index_profile(profile_id, model).outcome == "indexed"
        assert service.index_job(job_id, model).outcome == "indexed"
        db.commit()
    with Session(engine) as db:
        rows = RetrievalService(db).jobs_for_user(db.get(User, user_id), 20)
        assert [row["job_id"] for row in rows] == [job_id]

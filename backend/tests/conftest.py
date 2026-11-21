import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-with-enough-length"
# Tests that cover automatic re-embedding enable it explicitly with a fake embedder.
os.environ["AUTO_REINDEX"] = "false"
# Startup cache warm-up runs its own session against the configured database; tests call it directly.
os.environ["WARM_JOB_CACHE_ON_STARTUP"] = "false"

from app.db import models  # noqa: F401, E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402


class DeterministicTestTokenizer:
    """Dependency-free character tokenizer; real pinned-tokenizer checks are separately gated."""
    def encode(self, value, add_special_tokens=True, **kwargs):
        ids = [ord(c) + 2 for c in value]
        return [0, *ids, 1] if add_special_tokens else ids

    def decode(self, ids, **kwargs):
        return "".join(chr(i - 2) for i in ids if i > 1)

    def num_special_tokens_to_add(self, **kwargs):
        return 2


@pytest.fixture(autouse=True)
def synthetic_retrieval_tokenizer(monkeypatch):
    # Ordinary service/FK tests must never load/download a model or tokenizer.
    monkeypatch.setattr("app.repositories.retrieval_repository.load_local_tokenizer",
                        lambda: DeterministicTestTokenizer())
    from app.repositories.retrieval_repository import clear_job_representation_cache
    clear_job_representation_cache()
    yield
    clear_job_representation_cache()


@pytest.fixture()
def fake_retrieval(monkeypatch):
    """Stand-in for pgvector retrieval, which SQLite cannot run.

    Profile readiness keeps its real rules, except that a profile with approved
    skills but no vector counts as ready. `order` (a list of job IDs) is the
    retrieval order; by default all processed jobs in ID order. `fresh` lists the
    job IDs with a current vector; by default every retrieved job.
    """
    from app.services.retrieval_service import RetrievalService

    state = {"order": None, "fresh": None, "indexed_profile": True}
    real_readiness = RetrievalService.profile_readiness

    def readiness(self, user):
        status, query = real_readiness(self, user)
        if status == "profile_not_indexed" and state["indexed_profile"]:
            return "ready", object()
        return status, query

    def retrieve(self, query, limit, sources=None, exclude_sources=None, keep=None):
        from sqlalchemy import select
        from app.db.models import Job
        processed = {job.id: job for job in self.db.scalars(select(Job).where(Job.status == "processed"))
                     if (sources is None or job.source in sources) and job.source not in (exclude_sources or ())}
        if keep is not None:
            processed = {job_id: job for job_id, job in processed.items() if keep(job)}
        order = state["order"] if state["order"] is not None else sorted(processed, key=str)
        rows = [{"rank": index, "job_id": job_id, "retrieval_similarity": 1.0 - index / 100}
                for index, job_id in enumerate((j for j in order if j in processed), start=1)]
        return rows[:limit]

    def fresh_job_ids(self, exclude_sources=None):
        if state["fresh"] is not None:
            return set(state["fresh"])
        return {row["job_id"] for row in retrieve(self, None, 10_000, exclude_sources=exclude_sources)}

    monkeypatch.setattr(RetrievalService, "profile_readiness", readiness)
    monkeypatch.setattr(RetrievalService, "retrieve", retrieve)
    monkeypatch.setattr(RetrievalService, "fresh_job_ids", fresh_job_ids)
    monkeypatch.setattr(RetrievalService, "ready_job_ids", fresh_job_ids)
    return state


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

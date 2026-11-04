import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-with-enough-length"

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

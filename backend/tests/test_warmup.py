"""Startup warm-up of the job representation cache (D059)."""
from contextlib import nullcontext

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import Job
from app.repositories import retrieval_repository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval import warmup
from app.services.retrieval_service import RetrievalService
from tests.conftest import DeterministicTestTokenizer


def _job(db, title, status="processed"):
    job = Job(title=title, description="Requirements\nPython", cleaned_description="Requirements\nPython",
              status=status, source="manual")
    db.add(job)
    db.commit()
    return job


def test_warmup_builds_ready_jobs_once_and_requests_reuse_them(db_session, monkeypatch):
    tokenizer = DeterministicTestTokenizer()  # one process-wide tokenizer, as in production
    monkeypatch.setattr("app.repositories.retrieval_repository.load_local_tokenizer", lambda: tokenizer)
    ready, not_ready = _job(db_session, "Ready"), _job(db_session, "No vector")
    monkeypatch.setattr(RetrievalService, "ready_job_ids", lambda self, exclude_sources=None: {ready.id})
    builds = []
    real = retrieval_repository.build_job_representation
    monkeypatch.setattr(retrieval_repository, "build_job_representation",
                        lambda *a, **k: builds.append(a[0]["title"]) or real(*a, **k))

    assert warmup.warm_job_representations(lambda: nullcontext(db_session))["warmed"] == 1
    assert builds == ["Ready"]
    RetrievalRepository(db_session).job_input(db_session.get(Job, ready.id))  # a later request: cache hit
    assert builds == ["Ready"]


def test_warmup_reports_a_missing_tokenizer_without_raising(db_session, monkeypatch):
    job = _job(db_session, "Ready")
    monkeypatch.setattr(RetrievalService, "ready_job_ids", lambda self, exclude_sources=None: {job.id})

    def missing():
        raise RuntimeError("Pinned local tokenizer unavailable")
    monkeypatch.setattr("app.repositories.retrieval_repository.load_local_tokenizer", missing)
    result = warmup.warm_job_representations(lambda: nullcontext(db_session))
    assert result["warmed"] == 0 and "unavailable" in result["error"]


def test_startup_starts_the_warmup_only_when_enabled(monkeypatch):
    from app.main import create_app

    started = []
    monkeypatch.setattr(warmup, "start_background_warmup", lambda: started.append(True))
    monkeypatch.setattr(settings, "WARM_JOB_CACHE_ON_STARTUP", False)
    with TestClient(create_app()):
        pass
    assert started == []
    monkeypatch.setattr(settings, "WARM_JOB_CACHE_ON_STARTUP", True)
    with TestClient(create_app()):
        pass
    assert started == [True]


def test_warmup_pauses_while_a_request_is_in_flight(db_session, monkeypatch):
    import threading
    import time

    job = _job(db_session, "Ready")
    monkeypatch.setattr(RetrievalService, "ready_job_ids", lambda self, exclude_sources=None: {job.id})
    warmup.request_started()
    try:
        thread = threading.Thread(target=warmup.warm_job_representations, args=(lambda: nullcontext(db_session),))
        thread.start()
        time.sleep(0.2)
        assert thread.is_alive()  # waiting for the request to finish
    finally:
        warmup.request_finished()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_middleware_counts_requests_only_when_warmup_is_enabled(monkeypatch):
    from app.main import create_app

    seen = []
    monkeypatch.setattr(warmup, "start_background_warmup", lambda: None)
    monkeypatch.setattr(warmup, "request_started", lambda: seen.append("start"))
    monkeypatch.setattr(warmup, "request_finished", lambda: seen.append("end"))
    monkeypatch.setattr(settings, "WARM_JOB_CACHE_ON_STARTUP", True)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
    assert seen == ["start", "end"]


def test_concurrent_first_tokenizer_loads_share_one_instance(monkeypatch):
    import functools
    import threading
    import time

    from app.retrieval import embedder

    loads = []

    class Slow:
        pass

    def fake_from_pretrained(*args, **kwargs):
        time.sleep(0.1)  # a slow load, as AutoTokenizer.from_pretrained is
        loads.append(1)
        return Slow()

    monkeypatch.setattr(embedder, "_load_local_tokenizer",
                        functools.lru_cache(maxsize=2)(lambda path=None: fake_from_pretrained()))
    results = []
    threads = [threading.Thread(target=lambda: results.append(embedder.load_local_tokenizer())) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # Without the lock each thread misses the cache and loads its own instance.
    assert len(loads) == 1 and len({id(item) for item in results}) == 1

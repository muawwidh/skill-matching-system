"""Warm the job representation cache in the background at startup.

The Jobs page checks the freshness of every retrieved job by building its
representation; the first request after a restart would build up to 100 of
them. This builds the representation of every processed job with a ready
vector once, in a daemon thread, so later requests hit the cache. Read-only:
the session is rolled back. Results are identical to building on demand.
The thread pauses while any HTTP request is in flight, so it never competes
with a request for the interpreter (measured: 6.3 s instead of 4.6 s for a
first Jobs page during an unpaused warm-up).
"""
import logging
import threading
import time

log = logging.getLogger("uvicorn.error")

_in_flight = 0
_in_flight_lock = threading.Lock()


def request_started() -> None:
    global _in_flight
    with _in_flight_lock:
        _in_flight += 1


def request_finished() -> None:
    global _in_flight
    with _in_flight_lock:
        _in_flight -= 1


def _wait_while_busy(poll: float = 0.02) -> None:
    while _in_flight > 0:
        time.sleep(poll)


def warm_job_representations(session_factory=None) -> dict:
    from sqlalchemy import select

    from app.db.models import Job
    from app.services.retrieval_service import RetrievalService

    if session_factory is None:
        from app.db.session import SessionLocal as session_factory
    started = time.perf_counter()
    warmed = 0
    with session_factory() as db:
        try:
            service = RetrievalService(db)
            ready = service.ready_job_ids()
            for job in db.scalars(select(Job).where(Job.id.in_(ready)).order_by(Job.id)) if ready else []:
                _wait_while_busy()
                service.repository.job_input(job)
                warmed += 1
        except RuntimeError as error:  # e.g. pinned tokenizer missing: requests report it themselves
            log.warning("Job representation warm-up skipped: %s", error)
            return {"warmed": warmed, "seconds": round(time.perf_counter() - started, 2), "error": str(error)}
        finally:
            db.rollback()
    result = {"warmed": warmed, "seconds": round(time.perf_counter() - started, 2)}
    log.info("Job representation cache warmed: %s jobs in %s s", result["warmed"], result["seconds"])
    return result


def warm_occupation_label_matrix(session_factory=None) -> int:
    """Load stored occupation label vectors into memory; computes no embeddings."""
    from app.taxonomy.occupation_embeddings import label_matrix

    if session_factory is None:
        from app.db.session import SessionLocal as session_factory
    _wait_while_busy()
    with session_factory() as db:
        try:
            return len(label_matrix(db).concept_ids)
        finally:
            db.rollback()


def start_background_warmup() -> threading.Thread:
    def run() -> None:
        try:
            warm_job_representations()
        except Exception:  # never take the server down for a cache
            log.warning("Job representation warm-up failed", exc_info=True)
        try:
            warm_occupation_label_matrix()
        except Exception:
            log.warning("Occupation label matrix warm-up failed", exc_info=True)

    thread = threading.Thread(target=run, name="job-representation-warmup", daemon=True)
    thread.start()
    return thread

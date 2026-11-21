"""Automatic re-embedding after a committed change (DECISIONS.md D046).

Every per-profile or per-job invalidation (`RetrievalRepository.invalidate_profile`,
`invalidate_job`, `invalidate_term`) records the owner on its SQLAlchemy session.
When that session commits, the recorded profiles and jobs are re-embedded
synchronously in a separate session, with the pinned local E5 model. A rollback
discards the record.

This covers CV/job processing, extraction review, taxonomy link changes, job
edits/archiving and CV deletion, because all of them already invalidate.
Release-wide invalidation (`invalidate_all`, after a taxonomy import) is not
recorded: bulk re-embedding stays with `python -m app.retrieval.cli index`.

If the model is not provisioned, nothing is embedded and the vectors stay
stale; the Jobs page then reports that the profile has no up-to-date embedding.
"""
import logging
import threading
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

PROFILES_KEY = "auto_reindex_profiles"
JOBS_KEY = "auto_reindex_jobs"
# Set on sessions that must not trigger re-embedding: the re-embedding session
# itself and the bulk indexing CLI.
DISABLED_KEY = "auto_reindex_disabled"

_lock = threading.Lock()
_embedder = None


def record(session: Session, owner_kind: str, owner_id: UUID) -> None:
    if session.info.get(DISABLED_KEY):
        return
    key = PROFILES_KEY if owner_kind == "profile" else JOBS_KEY
    session.info.setdefault(key, set()).add(owner_id)


def get_embedder():
    """The process-wide pinned E5 embedder, loaded on first use.

    Raises RuntimeError if the model is not provisioned. A failure is not cached,
    so provisioning the model later takes effect without a restart.
    """
    global _embedder
    if _embedder is None:
        from app.retrieval.embedder import default_embedder
        _embedder = default_embedder()
    return _embedder


def reindex(bind, profile_ids: set[UUID], job_ids: set[UUID]) -> dict[str, int]:
    """Re-embed the given profiles and jobs; returns outcome counts. Never raises."""
    from app.repositories.retrieval_repository import RetrievalRepository
    from app.services.retrieval_service import RetrievalService

    counts = {"indexed": 0, "unchanged": 0, "not_ready": 0, "failed": 0, "skipped": 0}
    with _lock:
        try:
            embedder = get_embedder()
        except Exception as exc:  # model missing or unloadable: vectors stay stale
            log.warning("Automatic re-embedding skipped: %s", exc)
            counts["skipped"] = len(profile_ids) + len(job_ids)
            return counts
        work = [("profile", item) for item in sorted(profile_ids, key=str)]
        work += [("job", item) for item in sorted(job_ids, key=str)]
        for kind, owner_id in work:
            try:
                with Session(bind=bind, info={DISABLED_KEY: True}) as db:
                    service = RetrievalService(db, None, embedder.tokenizer)
                    outcome = (service.index_profile(owner_id, embedder) if kind == "profile"
                               else service.index_job(owner_id, embedder))
                    db.commit()
                counts[outcome.outcome] += 1
            except Exception as exc:
                counts["failed"] += 1
                log.warning("Automatic re-embedding of %s %s failed: %s", kind, owner_id, exc)
                with Session(bind=bind, info={DISABLED_KEY: True}) as db:
                    RetrievalRepository(db).mark_failed(owner_id, kind)
                    db.commit()
    return counts


@event.listens_for(Session, "after_commit")
def _reindex_after_commit(session: Session) -> None:
    if session.info.get(DISABLED_KEY):
        return
    profiles = session.info.pop(PROFILES_KEY, set())
    jobs = session.info.pop(JOBS_KEY, set())
    if not profiles and not jobs:
        return
    from app.core.config import settings
    if not settings.AUTO_REINDEX:
        return
    reindex(session.get_bind(), profiles, jobs)


@event.listens_for(Session, "after_rollback")
def _discard_after_rollback(session: Session) -> None:
    session.info.pop(PROFILES_KEY, None)
    session.info.pop(JOBS_KEY, None)

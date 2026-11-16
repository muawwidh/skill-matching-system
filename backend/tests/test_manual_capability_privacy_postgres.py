"""Fresh-session candidate privacy checks, synthetic disposable PostgreSQL only."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.models.explainable import SkillGapAtomicResult
from app.services.matching_runs_service import MatchingRunsService
from test_manual_capability_privacy import prepare, check_new_and_historical, assert_private_absent, PRIVATE
from test_matching_runs import table_snapshot
from test_taxonomy_postgres import pg_database  # noqa: F401


def test_private_metadata_filtering_fresh_session_preserves_history(pg_database):
    engine, _, _ = pg_database
    with Session(engine) as db:
        users, job, cap = prepare(db)
        rid, uid = check_new_and_historical(db, users, job, cap)
    with Session(engine) as db:
        before = table_snapshot(db)
        response = MatchingRunsService(db).read(db.get(User, uid), rid)
        assert_private_absent(response)
        assert table_snapshot(db) == before
        # Filtering is projection only, not cleanup of existing history.
        stored = db.scalars(select(SkillGapAtomicResult)).all()
        assert stored and all(x.reason_parameters["ledger_reference"] == PRIVATE["ledger_reference"] for x in stored)

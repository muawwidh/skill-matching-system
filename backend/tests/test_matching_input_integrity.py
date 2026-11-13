"""Offline/SQLite checks; PostgreSQL remains the exact-arithmetic authority."""
from importlib import import_module
from io import StringIO
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models.explainable import MatchScoreComponent


@pytest.fixture
def component_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()


@pytest.mark.parametrize("numerator,denominator,exact,value,valid", [
    (None, None, None, None, True), (0, 1, "0/1", 0, True),
    (None, 1, "1/1", 1, False), (1, None, "1/1", 1, False),
    (1, 1, None, None, False), (None, None, "1/1", 1, False),
    (None, None, None, 0, False), (1, 1, "1/1", None, False),
])
def test_component_ratio_nulls_on_model_schema(component_db, numerator, denominator, exact, value, valid):
    component_db.add(MatchScoreComponent(result_id=uuid4(), component="R", status="unassessed",
        applicability="applicable", numerator=numerator, denominator=denominator, base_weight=7,
        value_fraction=exact, value=value, reason_code="synthetic", reason_parameters={}))
    if valid:
        component_db.flush()
    else:
        with pytest.raises(IntegrityError):
            component_db.flush()
        component_db.rollback()


def test_0010_offline_upgrade_and_downgrade_cover_every_gate(monkeypatch):
    # SQL generation only: never connects to this placeholder or any runtime DB.
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+psycopg://unused/phase5_verify")
    migration = import_module("app.db.migrations.versions.0010_matching_input_integrity")
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "0009_explainable_matching:0010_matching_input_integrity", sql=True)
    sql = output.getvalue()
    assert "pg_advisory_xact_lock(603402)" in sql
    assert "ck_component_ratio_exact" in sql and "split_part(value_fraction" in sql
    assert "UPDATE job_match_results SET status = 'stale'" in sql
    assert "r.is_current AND r.status = 'current'" in sql
    assert "UPDATE candidate_skills" not in sql and "UPDATE job_embeddings" not in sql
    for table, scope in migration.INPUT_TABLES.items():
        assert f"BEFORE INSERT OR UPDATE OR DELETE ON {table} " in sql
        assert f"AFTER INSERT OR UPDATE OR DELETE ON {table} " in sql
        assert f"phase6_invalidate_inputs('{scope}')" in sql
    output.seek(0)
    output.truncate()
    command.downgrade(config, "0010_matching_input_integrity:0009_explainable_matching", sql=True)
    sql = output.getvalue()
    for table in migration.INPUT_TABLES:
        assert f"DROP TRIGGER phase6_input_gate ON {table}" in sql
        assert f"DROP TRIGGER phase6_input_invalidate ON {table}" in sql
    assert "DROP FUNCTION phase6_input_gate()" in sql

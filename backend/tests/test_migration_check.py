import json
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.utils.check_migrations import check_migrations, compare_heads
from test_taxonomy_postgres import pg_database  # noqa: F401


def test_backend_startup_has_read_only_guard_and_opt_in_migration_service():
    repository = Path(__file__).resolve().parents[2]
    dockerfile = (repository / "backend" / "Dockerfile").read_text(encoding="utf-8")
    instructions = re.findall(r"(?m)^(CMD|ENTRYPOINT)\s+(.+)$", dockerfile)
    assert len(instructions) == 1
    startup = json.loads(instructions[0][1])
    assert startup[:2] == ["sh", "-c"]
    assert re.search(
        r"python -m app\.utils\.check_migrations\s*&&\s*exec uvicorn\b",
        startup[2],
    )
    assert not re.search(r"\balembic\s+upgrade\b", startup[2])

    compose = (repository / "docker-compose.yml").read_text(encoding="utf-8")
    services = compose.partition("\nservices:\n")[2].partition("\nvolumes:\n")[0]
    assert services
    starts = list(re.finditer(r"(?m)^  ([a-z][a-z0-9_-]*):\s*$", services))
    blocks = {
        match.group(1): services[match.end():starts[index + 1].start() if index + 1 < len(starts) else len(services)]
        for index, match in enumerate(starts)
    }
    assert {"backend", "migrate"} <= blocks.keys()
    assert not re.search(r"(?m)^    (?:command|entrypoint):", blocks["backend"])
    assert re.search(r'(?m)^    profiles:\s*\["maintenance"\]\s*$', blocks["migrate"])
    migrate_command = re.search(r"(?m)^    command:\s*(\[[^\n]+\])\s*$", blocks["migrate"])
    assert migrate_command and json.loads(migrate_command.group(1)) == ["alembic", "upgrade", "head"]
    for name, block in blocks.items():
        if name == "migrate":
            continue
        directives = re.findall(r"(?m)^    (?:command|entrypoint):[^\n]*", block)
        assert all(not re.search(r"\balembic\b.*\bupgrade\b", directive) for directive in directives)


@pytest.mark.parametrize(
    ("repository", "database", "expected"),
    [
        ({"0008_dense_retrieval"}, {"0008_dense_retrieval"}, True),
        ({"head_a", "head_b"}, {"head_b", "head_a"}, True),
        ({"head_a", "head_b"}, {"head_a"}, False),
        ({"head_a"}, {"head_a", "unknown"}, False),
        ({"0008_dense_retrieval"}, {"0007_taxonomy_review_audit"}, False),
        ({"0008_dense_retrieval"}, set(), False),
        (set(), set(), False),
    ],
)
def test_compare_complete_head_sets(repository, database, expected):
    ok, message = compare_heads(repository, database)
    assert ok is expected
    assert "backend not started" in message if not ok else "matches repository" in message


def test_sqlite_revision_check_does_not_write_and_rejects_uninitialized_or_unknown(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'revisions.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sentinel (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO sentinel (value) VALUES ('unchanged')"))
    ok, message = check_migrations(url)
    assert not ok and "uninitialized" in message

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0008_dense_retrieval')"))
    assert check_migrations(url)[0]
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'unknown_future_revision'"))
    ok, message = check_migrations(url)
    assert not ok and "unknown_future_revision" in message
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT value FROM sentinel")) == "unchanged"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "unknown_future_revision"
    engine.dispose()


def test_unreachable_database_error_omits_credentials():
    url = "postgresql+psycopg://secret_user:secret_password@127.0.0.1:1/no_database?connect_timeout=1"
    ok, message = check_migrations(url)
    assert not ok and "Cannot read database revision" in message
    assert "secret_user" not in message and "secret_password" not in message and url not in message


def test_postgres_at_head_and_behind_are_read_only(pg_database):
    engine, config, _ = pg_database
    url = settings.DATABASE_URL
    assert check_migrations(url)[0]
    command.downgrade(config, "0007_taxonomy_review_audit")
    with engine.connect() as connection:
        before = connection.scalar(text("SELECT version_num FROM alembic_version"))
        count_before = connection.scalar(text("SELECT count(*) FROM users"))
    ok, message = check_migrations(url)
    assert not ok and "0007_taxonomy_review_audit" in message and "0008_dense_retrieval" in message
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == before
        assert connection.scalar(text("SELECT count(*) FROM users")) == count_before


def test_postgres_fresh_database_requires_explicit_upgrade_and_retry_is_safe(pg_database):
    engine, config, _ = pg_database
    command.downgrade(config, "base")
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_heads() == ()
    ok, message = check_migrations(settings.DATABASE_URL)
    assert not ok and "uninitialized" in message
    command.upgrade(config, "head")
    assert check_migrations(settings.DATABASE_URL)[0]
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0008_dense_retrieval"

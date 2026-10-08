"""Refuse to serve when the database and repository Alembic heads differ."""

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def compare_heads(repository_heads: set[str], database_heads: set[str]) -> tuple[bool, str]:
    if not repository_heads:
        return False, "Repository has no Alembic head; backend not started. Check migration files."
    if repository_heads == database_heads:
        return True, f"Database revision matches repository: {', '.join(sorted(repository_heads))}."
    if not database_heads:
        return False, "Database is uninitialized; backend not started. Run migrations explicitly before serving."
    return False, (
        f"Database revision(s) {', '.join(sorted(database_heads))} do not match repository head(s) "
        f"{', '.join(sorted(repository_heads))}; backend not started. Inspect revisions and run migrations "
        "explicitly after a backup if an upgrade is appropriate."
    )


def check_migrations(database_url: str) -> tuple[bool, str]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app/db/migrations"))
    repository_heads = set(ScriptDirectory.from_config(config).get_heads())
    engine = None
    try:
        engine = create_engine(database_url, poolclass=NullPool)
        with engine.connect() as connection:
            database_heads = set(MigrationContext.configure(connection).get_current_heads())
    except SQLAlchemyError:
        return False, "Cannot read database revision; backend not started. Check database availability and DATABASE_URL."
    finally:
        if engine is not None:
            engine.dispose()
    return compare_heads(repository_heads, database_heads)


def main() -> int:
    ok, message = check_migrations(settings.DATABASE_URL)
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

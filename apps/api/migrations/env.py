"""Alembic environment for Auralith.

The database URL comes from AURALITH_DB_URL (the same variable the API reads), so
migrations always target the database the app uses. Models are imported from
apps/api/models.py, which has no import-time side effects.
"""

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

HERE = Path(__file__).resolve()


def _import_roots(start: Path, depth: int = 4) -> list[Path]:
    """Candidate import roots for both supported layouts.

    The repository root (apps/api/migrations) and the API directory built on its own
    (/app/migrations, where app.py is the module and there is no apps/ package).
    Walking up avoids IndexError from a short parents sequence.
    """
    roots, current = [start], start
    for _ in range(depth):
        if current.parent == current:
            break
        current = current.parent
        roots.append(current)
    return roots


for candidate in _import_roots(HERE.parent):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from apps.api.infrastructure.database.sqlalchemy_provider import (  # noqa: E402
    SQLAlchemyDatabaseProvider,
)
from apps.api.models import Base  # noqa: E402

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    url = os.getenv("AURALITH_DB_URL", "").strip()
    if not url:
        data_dir = Path(os.getenv("AURALITH_DATA_DIR", "./data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{data_dir / 'auralith.db'}"
    url = SQLAlchemyDatabaseProvider.normalize_url(url)
    ensure_sqlite_directory(url)
    return url


def ensure_sqlite_directory(url: str) -> None:
    """SQLite cannot create missing directories, and a fresh volume has none."""
    if not url.startswith("sqlite") or ":///" not in url:
        return
    target = Path(url.split(":///", 1)[1])
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)


def configure(connection=None) -> None:
    url = database_url()
    options = {
        "target_metadata": target_metadata,
        "compare_type": True,
        # SQLite cannot ALTER most columns in place; batch mode rewrites the table.
        "render_as_batch": url.startswith("sqlite"),
    }
    if connection is None:
        context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **options)
    else:
        context.configure(connection=connection, **options)


def run_migrations_offline() -> None:
    configure()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        configure(connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

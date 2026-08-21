"""Alembic environment for the BlackBox database.

Run programmatically via blackbox_api.storage.db.init_db() at startup, or
from the CLI with apps/api/alembic.ini. The database URL comes from the
config's sqlalchemy.url (set by init_db) or BLACKBOX_DATABASE_URL.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine

from blackbox_api.storage.models import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return os.environ.get(
        "BLACKBOX_DATABASE_URL", "sqlite:///./data/blackbox.db"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        engine = create_engine(_database_url())
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()
    else:
        context.configure(
            connection=connectable, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

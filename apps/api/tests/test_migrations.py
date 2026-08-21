from __future__ import annotations

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from blackbox_api.storage.db import init_db
from blackbox_api.storage.models import Base


def test_migrations_produce_the_model_schema(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/migrated.db")
    init_db(engine)

    inspector = inspect(engine)
    expected = set(Base.metadata.tables) | {"alembic_version"}
    assert set(inspector.get_table_names()) == expected

    # Column-level parity, and no drift the models would autogenerate away.
    for table_name, table in Base.metadata.tables.items():
        columns = {c["name"] for c in inspector.get_columns(table_name)}
        assert columns == {c.name for c in table.columns}, table_name
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []
    engine.dispose()


def test_legacy_create_all_database_is_stamped(tmp_path: Path) -> None:
    """A pre-Alembic database adopts migrations without re-creating tables."""
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    Base.metadata.create_all(engine)

    init_db(engine)  # must stamp, not fail on existing tables

    inspector = inspect(engine)
    assert inspector.has_table("alembic_version")
    # Idempotent: a second init is a no-op.
    init_db(engine)
    engine.dispose()


def test_init_db_is_repeatable(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    init_db(engine)
    init_db(engine)
    assert inspect(engine).has_table("incidents")
    engine.dispose()

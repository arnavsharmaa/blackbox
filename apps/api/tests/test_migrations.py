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


def test_chunk_migration_carries_sample_data(tmp_path: Path) -> None:
    """Upgrading a 0001-era database converts sample rows into chunks."""
    from alembic import command
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from blackbox_api.storage.db import _alembic_config
    from blackbox_api.storage.repository import IncidentRepository

    engine = create_engine(f"sqlite:///{tmp_path}/rowwise.db")
    config = _alembic_config(engine)
    command.upgrade(config, "0001")

    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO incidents (id, schema_version, robot_id,"
            " robot_model, facility, task_name, task_goal, start_time,"
            " end_time, duration_s, outcome, severity, software_version,"
            " map_version, environment, summary, created_at) VALUES"
            " ('INC-OLD-1', '1.0', 'W-1', 'M', 'F', 'T', 'G',"
            " '2026-07-01 10:00:00', '2026-07-01 10:01:00', 60.0,"
            " 'failed', 'error', 'v1', 'm1', 'env', 'legacy row-wise',"
            " '2026-07-01 10:02:00')"
        ))
        connection.execute(text(
            "INSERT INTO events (incident_id, idx, timestamp, event_type,"
            " subsystem, severity, message, payload_json,"
            " evidence_tags_json) VALUES ('INC-OLD-1', 0,"
            " '2026-07-01 10:00:30', 'task_failed', 'task_manager',"
            " 'error', 'failed', '{}', '[]')"
        ))
        for i in range(3):
            connection.execute(text(
                "INSERT INTO telemetry_samples (incident_id, channel,"
                " unit, t, value_num, value_str) VALUES"
                f" ('INC-OLD-1', 'pos_x', 'm', {float(i)}, {i * 0.5}, NULL)"
            ))
        connection.execute(text(
            "INSERT INTO telemetry_samples (incident_id, channel, unit,"
            " t, value_num, value_str) VALUES"
            " ('INC-OLD-1', 'planner_state', '', 0.0, NULL, 'executing')"
        ))

    command.upgrade(config, "head")

    with Session(engine) as session:
        incident = IncidentRepository(session).get_incident("INC-OLD-1")
    assert incident is not None
    by_channel = {s.channel.value: s for s in incident.telemetry}
    assert [s.value for s in by_channel["pos_x"].samples] == [0.0, 0.5, 1.0]
    assert by_channel["planner_state"].samples[0].value == "executing"
    engine.dispose()


def test_init_db_is_repeatable(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    init_db(engine)
    init_db(engine)
    assert inspect(engine).has_table("incidents")
    engine.dispose()

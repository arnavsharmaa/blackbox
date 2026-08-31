from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from blackbox_api.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # Ensure the parent directory for a file-backed SQLite DB exists.
        path_part = database_url.split("///", 1)[-1]
        if path_part and path_part != ":memory:":
            Path(path_part).expanduser().resolve().parent.mkdir(
                parents=True, exist_ok=True
            )
        engine = create_engine(
            database_url, connect_args={"check_same_thread": False}
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(database_url)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
    return _engine


def _alembic_config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option(
        "sqlalchemy.url", engine.url.render_as_string(hide_password=False)
    )
    return config


def init_db(engine: Engine | None = None) -> None:
    """Repeatable database initialization via Alembic migrations.

    Databases created by the pre-Alembic create_all() bootstrap are
    stamped to the initial revision first, then upgraded like any other.
    """
    eng = engine or get_engine()
    inspector = inspect(eng)
    config = _alembic_config(eng)
    if inspector.has_table("incidents") and not inspector.has_table(
        "alembic_version"
    ):
        # Pre-Alembic databases still carry the row-per-sample telemetry
        # table and must replay the 0002 data migration; a database built
        # by create_all() from current models already matches head.
        legacy = inspector.has_table("telemetry_samples")
        command.stamp(config, "0001" if legacy else "head")
    command.upgrade(config, "head")


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _session_factory


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    get_settings.cache_clear()

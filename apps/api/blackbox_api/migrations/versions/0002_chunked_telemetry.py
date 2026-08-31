"""Chunked telemetry: one row per channel instead of one per sample.

Existing sample rows are carried over into JSON chunks, then the
row-per-sample table is dropped. Downgrade expands the chunks back.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_series",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=48), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("samples_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_series_incident_channel",
        "telemetry_series",
        ["incident_id", "channel"],
        unique=True,
    )
    op.create_index(
        op.f("ix_telemetry_series_incident_id"),
        "telemetry_series",
        ["incident_id"],
        unique=False,
    )

    # Carry existing samples over as per-channel chunks.
    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT incident_id, channel, unit, t, value_num, value_str "
        "FROM telemetry_samples ORDER BY incident_id, channel, t"
    )).fetchall()
    units: dict[tuple[str, str], str] = {}
    chunks: dict[tuple[str, str], list[list[float | str]]] = {}
    for incident_id, channel, unit, t, value_num, value_str in rows:
        key = (incident_id, channel)
        units.setdefault(key, unit)
        value = value_str if value_str is not None else (value_num or 0.0)
        chunks.setdefault(key, []).append([t, value])
    if chunks:
        op.bulk_insert(
            sa.table(
                "telemetry_series",
                sa.column("incident_id", sa.String),
                sa.column("channel", sa.String),
                sa.column("unit", sa.String),
                sa.column("samples_json", sa.Text),
            ),
            [
                {
                    "incident_id": incident_id,
                    "channel": channel,
                    "unit": units[(incident_id, channel)],
                    "samples_json": json.dumps(samples),
                }
                for (incident_id, channel), samples in chunks.items()
            ],
        )

    op.drop_index(
        op.f("ix_telemetry_samples_incident_id"),
        table_name="telemetry_samples",
    )
    op.drop_index(
        "ix_telemetry_incident_channel_t", table_name="telemetry_samples"
    )
    op.drop_table("telemetry_samples")


def downgrade() -> None:
    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=48), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("t", sa.Float(), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_str", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_incident_channel_t",
        "telemetry_samples",
        ["incident_id", "channel", "t"],
        unique=False,
    )
    op.create_index(
        op.f("ix_telemetry_samples_incident_id"),
        "telemetry_samples",
        ["incident_id"],
        unique=False,
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT incident_id, channel, unit, samples_json "
        "FROM telemetry_series"
    )).fetchall()
    expanded = [
        {
            "incident_id": incident_id,
            "channel": channel,
            "unit": unit,
            "t": t,
            "value_num": value if not isinstance(value, str) else None,
            "value_str": value if isinstance(value, str) else None,
        }
        for incident_id, channel, unit, samples_json in rows
        for t, value in json.loads(samples_json)
    ]
    if expanded:
        op.bulk_insert(
            sa.table(
                "telemetry_samples",
                sa.column("incident_id", sa.String),
                sa.column("channel", sa.String),
                sa.column("unit", sa.String),
                sa.column("t", sa.Float),
                sa.column("value_num", sa.Float),
                sa.column("value_str", sa.String),
            ),
            expanded,
        )

    op.drop_index(
        "ix_telemetry_series_incident_channel", table_name="telemetry_series"
    )
    op.drop_index(
        op.f("ix_telemetry_series_incident_id"),
        table_name="telemetry_series",
    )
    op.drop_table("telemetry_series")

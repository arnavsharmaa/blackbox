"""Initial schema: incidents, events, telemetry, analyses, feedback.

Matches the SQLAlchemy models at the point Alembic was adopted; databases
created earlier by create_all() are stamped to this revision by init_db().

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("robot_id", sa.String(length=64), nullable=False),
        sa.Column("robot_model", sa.String(length=128), nullable=False),
        sa.Column("facility", sa.String(length=128), nullable=False),
        sa.Column("task_name", sa.String(length=256), nullable=False),
        sa.Column("task_goal", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("software_version", sa.String(length=64), nullable=False),
        sa.Column("map_version", sa.String(length=64), nullable=False),
        sa.Column("environment", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_incidents_outcome"), "incidents", ["outcome"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_robot_id"), "incidents", ["robot_id"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_severity"), "incidents", ["severity"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_start_time"),
        "incidents",
        ["start_time"],
        unique=False,
    )

    op.create_table(
        "analyses",
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("incident_id"),
    )

    op.create_table(
        "diagnosis_feedback",
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("diagnosed_category", sa.String(length=48), nullable=False),
        sa.Column("actual_category", sa.String(length=48), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("incident_id"),
    )
    op.create_index(
        op.f("ix_diagnosis_feedback_diagnosed_category"),
        "diagnosis_feedback",
        ["diagnosed_category"],
        unique=False,
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("subsystem", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_tags_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_events_event_type"), "events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_events_incident_id"), "events", ["incident_id"], unique=False
    )

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


def downgrade() -> None:
    op.drop_index(
        op.f("ix_telemetry_samples_incident_id"),
        table_name="telemetry_samples",
    )
    op.drop_index(
        "ix_telemetry_incident_channel_t", table_name="telemetry_samples"
    )
    op.drop_table("telemetry_samples")
    op.drop_index(op.f("ix_events_incident_id"), table_name="events")
    op.drop_index(op.f("ix_events_event_type"), table_name="events")
    op.drop_table("events")
    op.drop_index(
        op.f("ix_diagnosis_feedback_diagnosed_category"),
        table_name="diagnosis_feedback",
    )
    op.drop_table("diagnosis_feedback")
    op.drop_table("analyses")
    op.drop_index(op.f("ix_incidents_start_time"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_severity"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_robot_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_outcome"), table_name="incidents")
    op.drop_table("incidents")

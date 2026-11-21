"""Triage state on incidents (open/investigating/resolved).

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column(
            "triage_state",
            sa.String(length=16),
            server_default="open",
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_incidents_triage_state"),
        "incidents",
        ["triage_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_incidents_triage_state"), table_name="incidents"
    )
    op.drop_column("incidents", "triage_state")

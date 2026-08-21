from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16))
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    robot_model: Mapped[str] = mapped_column(String(128))
    facility: Mapped[str] = mapped_column(String(128))
    task_name: Mapped[str] = mapped_column(String(256))
    task_goal: Mapped[str] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    software_version: Mapped[str] = mapped_column(String(64))
    map_version: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    events: Mapped[list[EventRow]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="EventRow.idx",
    )
    telemetry: Mapped[list[TelemetrySampleRow]] = relationship(
        cascade="all, delete-orphan",
    )
    analysis: Mapped[AnalysisRow | None] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    feedback: Mapped[FeedbackRow | None] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    subsystem: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_tags_json: Mapped[str] = mapped_column(Text, default="[]")

    incident: Mapped[IncidentRow] = relationship(back_populates="events")


class TelemetrySampleRow(Base):
    __tablename__ = "telemetry_samples"
    __table_args__ = (
        Index("ix_telemetry_incident_channel_t", "incident_id", "channel", "t"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(48))
    unit: Mapped[str] = mapped_column(String(24), default="")
    t: Mapped[float] = mapped_column(Float)
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_str: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AnalysisRow(Base):
    __tablename__ = "analyses"

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    engine_version: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[str] = mapped_column(Text)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped[IncidentRow] = relationship(back_populates="analysis")


class FeedbackRow(Base):
    """One engineer verdict per incident; re-submitting replaces it."""

    __tablename__ = "diagnosis_feedback"

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(16))
    diagnosed_category: Mapped[str] = mapped_column(String(48), index=True)
    actual_category: Mapped[str | None] = mapped_column(
        String(48), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped[IncidentRow] = relationship(back_populates="feedback")

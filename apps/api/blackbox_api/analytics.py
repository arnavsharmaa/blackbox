"""Cross-incident fleet analytics.

Aggregates recorded incidents into fleet-level views: category and outcome
mix, per-robot and per-software-version failure counts (regression
detection), daily trends, and recurring obstacle-blockage locations. All
aggregation happens over the repository at request time — fine at
SQLite/MVP scale; a warehouse-sized deployment would precompute these.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import BaseModel, ConfigDict

from blackbox_api.schemas import FailureCategory, IncidentSummary, Outcome
from blackbox_api.storage.repository import IncidentFilters, IncidentRepository

#: Obstacle positions within this grid size (meters) count as one hotspot.
HOTSPOT_GRID_M = 0.5


class CategoryCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    count: int


class OutcomeCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Outcome
    count: int


class RobotStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    robot_id: str
    robot_model: str
    incidents: int
    critical: int
    recovery_attempts: int
    top_category: FailureCategory | None


class VersionStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    software_version: str
    incidents: int
    categories: list[CategoryCount]


class BlockageHotspot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility: str
    x: float
    y: float
    count: int
    incident_ids: list[str]


class DailyCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    category: FailureCategory
    count: int


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_incidents: int
    critical_incidents: int
    total_recovery_attempts: int
    categories: list[CategoryCount]
    outcomes: list[OutcomeCount]
    by_robot: list[RobotStats]
    by_software_version: list[VersionStats]
    blockage_hotspots: list[BlockageHotspot]
    daily: list[DailyCount]


def _top_category(
    summaries: list[IncidentSummary],
) -> FailureCategory | None:
    counts = Counter(
        s.failure_category for s in summaries if s.failure_category
    )
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _blockage_hotspots(
    repo: IncidentRepository, summaries: list[IncidentSummary]
) -> list[BlockageHotspot]:
    """Cluster obstacle positions of obstacle-blockage incidents on a grid."""
    clusters: dict[tuple[str, float, float], list[str]] = defaultdict(list)
    for summary in summaries:
        if summary.failure_category != FailureCategory.PERSISTENT_OBSTACLE:
            continue
        incident = repo.get_incident(summary.id)
        if incident is None:
            continue
        for event in incident.events:
            x = event.payload.get("obstacle_x")
            y = event.payload.get("obstacle_y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                key = (
                    incident.facility,
                    round(float(x) / HOTSPOT_GRID_M) * HOTSPOT_GRID_M,
                    round(float(y) / HOTSPOT_GRID_M) * HOTSPOT_GRID_M,
                )
                if summary.id not in clusters[key]:
                    clusters[key].append(summary.id)
                break
    hotspots = [
        BlockageHotspot(
            facility=facility, x=x, y=y, count=len(ids), incident_ids=ids
        )
        for (facility, x, y), ids in clusters.items()
    ]
    hotspots.sort(key=lambda h: (-h.count, h.facility, h.x, h.y))
    return hotspots


def compute_analytics(repo: IncidentRepository) -> AnalyticsResponse:
    summaries, _total = repo.list_incidents(IncidentFilters(), limit=1000)

    category_counts = Counter(
        s.failure_category for s in summaries if s.failure_category
    )
    outcome_counts = Counter(s.outcome for s in summaries)

    by_robot: list[RobotStats] = []
    robots: dict[str, list[IncidentSummary]] = defaultdict(list)
    for summary in summaries:
        robots[summary.robot_id].append(summary)
    for robot_id in sorted(robots):
        items = robots[robot_id]
        by_robot.append(RobotStats(
            robot_id=robot_id,
            robot_model=items[0].robot_model,
            incidents=len(items),
            critical=sum(1 for s in items if s.severity.value == "critical"),
            recovery_attempts=sum(s.recovery_attempts for s in items),
            top_category=_top_category(items),
        ))

    by_version: list[VersionStats] = []
    versions: dict[str, list[IncidentSummary]] = defaultdict(list)
    for summary in summaries:
        versions[summary.software_version].append(summary)
    for version in sorted(versions):
        items = versions[version]
        version_categories = Counter(
            s.failure_category for s in items if s.failure_category
        )
        by_version.append(VersionStats(
            software_version=version,
            incidents=len(items),
            categories=[
                CategoryCount(category=category, count=count)
                for category, count in sorted(
                    version_categories.items(), key=lambda kv: -kv[1]
                )
            ],
        ))

    daily_counts: Counter[tuple[str, FailureCategory]] = Counter()
    for summary in summaries:
        if summary.failure_category:
            day = summary.start_time.date().isoformat()
            daily_counts[(day, summary.failure_category)] += 1

    return AnalyticsResponse(
        total_incidents=len(summaries),
        critical_incidents=sum(
            1 for s in summaries if s.severity.value == "critical"
        ),
        total_recovery_attempts=sum(s.recovery_attempts for s in summaries),
        categories=[
            CategoryCount(category=category, count=count)
            for category, count in sorted(
                category_counts.items(), key=lambda kv: -kv[1]
            )
        ],
        outcomes=[
            OutcomeCount(outcome=outcome, count=count)
            for outcome, count in sorted(
                outcome_counts.items(), key=lambda kv: -kv[1]
            )
        ],
        by_robot=by_robot,
        by_software_version=by_version,
        blockage_hotspots=_blockage_hotspots(repo, summaries),
        daily=sorted(
            (
                DailyCount(date=day, category=category, count=count)
                for (day, category), count in daily_counts.items()
            ),
            key=lambda d: (d.date, d.category.value),
        ),
    )

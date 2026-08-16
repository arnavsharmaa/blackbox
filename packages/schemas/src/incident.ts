/**
 * Canonical BlackBox incident schema — TypeScript mirror.
 *
 * Source of truth: apps/api/blackbox_api/schemas/incident.py (Pydantic).
 * apps/api/tests/test_schema_sync.py verifies the enum values and field names
 * here stay in sync with the backend. Update both together.
 */

export const SCHEMA_VERSION = "1.0";

export type Severity = "info" | "warning" | "error" | "critical";

export type Outcome = "success" | "failed" | "timed_out" | "aborted";

export type FailureCategory =
  | "persistent_obstacle"
  | "localization_failure"
  | "controller_oscillation"
  | "sensor_dropout"
  | "unknown";

export type Subsystem =
  | "task_manager"
  | "navigation"
  | "planner"
  | "controller"
  | "localization"
  | "perception"
  | "system";

export type EventType =
  | "task_started"
  | "nav_goal_issued"
  | "pose_updated"
  | "velocity_command"
  | "planner_state_changed"
  | "obstacle_distance_updated"
  | "recovery_started"
  | "recovery_completed"
  | "warning_raised"
  | "error_raised"
  | "task_timed_out"
  | "task_failed";

export type TelemetryChannel =
  | "pos_x"
  | "pos_y"
  | "heading"
  | "linear_velocity"
  | "angular_velocity"
  | "obstacle_distance"
  | "goal_distance"
  | "localization_confidence"
  | "planner_state"
  | "recovery_count"
  | "battery_pct";

export interface IncidentEvent {
  timestamp: string;
  event_type: EventType;
  subsystem: Subsystem;
  severity: Severity;
  message: string;
  payload: Record<string, unknown>;
  correlation_id: string | null;
  evidence_tags: string[];
}

export interface TelemetrySample {
  t: number;
  value: number | string;
}

export interface TelemetrySeries {
  channel: TelemetryChannel;
  unit: string;
  samples: TelemetrySample[];
}

export interface Incident {
  schema_version: string;
  id: string;
  robot_id: string;
  robot_model: string;
  facility: string;
  task_name: string;
  task_goal: string;
  start_time: string;
  end_time: string;
  outcome: Outcome;
  severity: Severity;
  software_version: string;
  map_version: string;
  environment: string;
  summary: string;
  events: IncidentEvent[];
  telemetry: TelemetrySeries[];
}

export interface EvidenceItem {
  id: string;
  summary: string;
  detail: string;
  t: number;
  t_end: number | null;
  channel: TelemetryChannel | null;
  tags: string[];
}

export interface AlternativeCause {
  category: FailureCategory;
  score: number;
  reason: string;
}

export interface AnalysisResult {
  incident_id: string;
  engine_version: string;
  failure_category: FailureCategory;
  confidence: number;
  explanation: string;
  recommended_actions: string[];
  evidence: EvidenceItem[];
  alternative_causes: AlternativeCause[];
  rules_triggered: string[];
  analyzed_at: string;
  ai_explanation: string | null;
}

export interface IncidentSummary {
  id: string;
  robot_id: string;
  robot_model: string;
  facility: string;
  task_name: string;
  start_time: string;
  end_time: string;
  duration_s: number;
  outcome: Outcome;
  severity: Severity;
  software_version: string;
  summary: string;
  event_count: number;
  recovery_attempts: number;
  failure_category: FailureCategory | null;
  confidence: number | null;
}

export interface IncidentDetail {
  incident: Incident;
  analysis: AnalysisResult | null;
}

export interface IncidentListResponse {
  items: IncidentSummary[];
  total: number;
  limit: number;
  offset: number;
}

/** Body of POST /api/incidents/upload success responses. */
export interface UploadResponse {
  incident_id: string;
  event_count: number;
  telemetry_channels: number;
  failure_category: FailureCategory;
  confidence: number;
}

/** Body of GET /api/incidents/{id}/github-issue. */
export interface GithubIssue {
  title: string;
  body: string;
  labels: string[];
  markdown: string;
  issue_url: string | null;
}

/** Shape of GET /api/incidents/{id}/report (subset used by the UI). */
export interface IncidentReport {
  report_version: string;
  incident: Record<string, string | number>;
  root_cause: {
    category: FailureCategory;
    category_label: string;
    confidence: number;
    explanation: string;
    rules_triggered: string[];
    engine_version: string;
  } | null;
  evidence: EvidenceItem[];
  recommended_actions: string[];
  alternative_causes: AlternativeCause[];
  timeline: {
    t: number;
    timestamp: string;
    event_type: EventType;
    subsystem: Subsystem;
    severity: Severity;
    message: string;
  }[];
  telemetry_summary: {
    channel: string;
    unit: string;
    min: number;
    max: number;
    last: number;
    samples: number;
  }[];
  reproduction: { notes: string; replay_url: string };
  ai_explanation: string | null;
  markdown: string;
}

/** Body of GET /api/analytics. */
export interface CategoryCount {
  category: FailureCategory;
  count: number;
}

export interface OutcomeCount {
  outcome: Outcome;
  count: number;
}

export interface RobotStats {
  robot_id: string;
  robot_model: string;
  incidents: number;
  critical: number;
  recovery_attempts: number;
  top_category: FailureCategory | null;
}

export interface VersionStats {
  software_version: string;
  incidents: number;
  categories: CategoryCount[];
}

export interface BlockageHotspot {
  facility: string;
  x: number;
  y: number;
  count: number;
  incident_ids: string[];
}

export interface DailyCount {
  date: string;
  category: FailureCategory;
  count: number;
}

export interface AnalyticsResponse {
  total_incidents: number;
  critical_incidents: number;
  total_recovery_attempts: number;
  categories: CategoryCount[];
  outcomes: OutcomeCount[];
  by_robot: RobotStats[];
  by_software_version: VersionStats[];
  blockage_hotspots: BlockageHotspot[];
  daily: DailyCount[];
}

/** Body of GET /api/incidents/{id}/diff/{baseline_id}. */
export interface RunRef {
  id: string;
  robot_id: string;
  task_name: string;
  outcome: Outcome;
  duration_s: number;
}

export interface ChannelDiff {
  channel: TelemetryChannel;
  /** Null for string channels, which diverge on any value mismatch. */
  delta_threshold: number | null;
  max_abs_delta: number | null;
  max_abs_delta_t: number | null;
  first_divergence_t: number | null;
}

export interface EventTypeDelta {
  event_type: EventType;
  incident_count: number;
  baseline_count: number;
}

export interface DiffResponse {
  incident: RunRef;
  baseline: RunRef;
  channels: ChannelDiff[];
  first_divergence_t: number | null;
  first_divergence_channel: TelemetryChannel | null;
  events: EventTypeDelta[];
  event_types_only_in_incident: EventType[];
}

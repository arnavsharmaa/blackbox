import type {
  AnalysisResult,
  Incident,
  IncidentListResponse,
  IncidentSummary,
} from "@blackbox/schemas";

const START = "2026-07-28T09:00:00Z";

function iso(offsetSeconds: number): string {
  return new Date(
    new Date(START).getTime() + offsetSeconds * 1000,
  ).toISOString();
}

export const testIncident: Incident = {
  schema_version: "1.0",
  id: "INC-TEST-100",
  robot_id: "W-104",
  robot_model: "Fetchbot AMR-600",
  facility: "Warehouse 3",
  task_name: "Deliver pallet to Loading Bay B",
  task_goal: "Reach Loading Bay B",
  start_time: iso(0),
  end_time: iso(60),
  outcome: "timed_out",
  severity: "critical",
  software_version: "nav-stack 2.14.1",
  map_version: "warehouse3-2026.07.12",
  environment: "Indoor warehouse",
  summary: "Robot blocked by pallet and timed out.",
  events: [
    {
      timestamp: iso(0),
      event_type: "task_started",
      subsystem: "task_manager",
      severity: "info",
      message: "Task started",
      payload: {},
      correlation_id: "T-1",
      evidence_tags: [],
    },
    {
      timestamp: iso(1),
      event_type: "nav_goal_issued",
      subsystem: "navigation",
      severity: "info",
      message: "Goal issued",
      payload: { goal_x: 18, goal_y: 6.5 },
      correlation_id: "T-1",
      evidence_tags: [],
    },
    {
      timestamp: iso(20),
      event_type: "warning_raised",
      subsystem: "planner",
      severity: "warning",
      message: "Obstacle below safety threshold",
      payload: { distance_m: 0.5, obstacle_x: 13.5, obstacle_y: 5.35 },
      correlation_id: "T-1",
      evidence_tags: ["obstacle"],
    },
    {
      timestamp: iso(50),
      event_type: "task_timed_out",
      subsystem: "task_manager",
      severity: "error",
      message: "Task timed out",
      payload: { timeout_s: 50 },
      correlation_id: "T-1",
      evidence_tags: ["timeout"],
    },
  ],
  telemetry: [
    {
      channel: "pos_x",
      unit: "m",
      samples: [
        { t: 0, value: 2 },
        { t: 30, value: 10 },
        { t: 60, value: 13 },
      ],
    },
    {
      channel: "pos_y",
      unit: "m",
      samples: [
        { t: 0, value: 2 },
        { t: 30, value: 3 },
        { t: 60, value: 5 },
      ],
    },
    {
      channel: "linear_velocity",
      unit: "m/s",
      samples: [
        { t: 0, value: 0 },
        { t: 10, value: 0.8 },
        { t: 40, value: 0 },
      ],
    },
    {
      channel: "obstacle_distance",
      unit: "m",
      samples: [
        { t: 0, value: 5 },
        { t: 30, value: 0.45 },
        { t: 60, value: 0.42 },
      ],
    },
    {
      channel: "localization_confidence",
      unit: "",
      samples: [
        { t: 0, value: 0.97 },
        { t: 60, value: 0.96 },
      ],
    },
  ],
};

export const testAnalysis: AnalysisResult = {
  incident_id: "INC-TEST-100",
  engine_version: "1.0.0",
  failure_category: "persistent_obstacle",
  confidence: 0.95,
  explanation: "The local planner could not find a path around the obstacle.",
  recommended_actions: ["Check the aisle for a stray pallet"],
  evidence: [
    {
      id: "e1",
      summary: "Obstacle distance remained below 0.60 m for 30.0 s",
      detail: "",
      t: 30,
      t_end: 60,
      channel: "obstacle_distance",
      tags: ["obstacle"],
    },
    {
      id: "e2",
      summary: "Task timed out at t=50.0 s",
      detail: "",
      t: 50,
      t_end: null,
      channel: null,
      tags: ["timeout"],
    },
  ],
  alternative_causes: [
    {
      category: "localization_failure",
      score: 0.15,
      reason: "Conditions met: navigation_failure",
    },
  ],
  rules_triggered: ["persistent_obstacle_blockage"],
  analyzed_at: iso(61),
  ai_explanation: null,
};

export const testSummaries: IncidentSummary[] = [
  {
    id: "INC-TEST-100",
    robot_id: "W-104",
    robot_model: "Fetchbot AMR-600",
    facility: "Warehouse 3",
    task_name: "Deliver pallet to Loading Bay B",
    start_time: iso(0),
    end_time: iso(60),
    duration_s: 60,
    outcome: "timed_out",
    severity: "critical",
    software_version: "nav-stack 2.14.1",
    summary: "Robot blocked by pallet and timed out.",
    event_count: 4,
    recovery_attempts: 3,
    failure_category: "persistent_obstacle",
    confidence: 0.95,
  },
  {
    id: "INC-TEST-101",
    robot_id: "W-087",
    robot_model: "Fetchbot AMR-600",
    facility: "Warehouse 3",
    task_name: "Return to charging dock",
    start_time: iso(-3600),
    end_time: iso(-3540),
    duration_s: 60,
    outcome: "failed",
    severity: "error",
    software_version: "nav-stack 2.14.1",
    summary: "Localization collapsed near racking.",
    event_count: 12,
    recovery_attempts: 1,
    failure_category: "localization_failure",
    confidence: 0.9,
  },
];

export function listResponse(
  items: IncidentSummary[] = testSummaries,
): IncidentListResponse {
  return { items, total: items.length, limit: 100, offset: 0 };
}

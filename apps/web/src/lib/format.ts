import type {
  EventType,
  FailureCategory,
  Outcome,
  Severity,
} from "@blackbox/schemas";

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest.toString().padStart(2, "0")}s`;
}

export function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m.toString().padStart(2, "0")}:${s}`;
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export const SEVERITY_STYLES: Record<Severity, string> = {
  info: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  warning: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  error: "bg-orange-600/15 text-orange-300 border-orange-500/30",
  critical: "bg-red-600/15 text-red-300 border-red-500/40",
};

export const OUTCOME_STYLES: Record<Outcome, string> = {
  success: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-600/15 text-red-300 border-red-500/40",
  timed_out: "bg-orange-600/15 text-orange-300 border-orange-500/30",
  aborted: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  success: "Success",
  failed: "Failed",
  timed_out: "Timed out",
  aborted: "Aborted",
};

export const CATEGORY_LABELS: Record<FailureCategory, string> = {
  persistent_obstacle: "Persistent obstacle",
  localization_failure: "Localization failure",
  controller_oscillation: "Controller oscillation",
  sensor_dropout: "Sensor dropout",
  unknown: "Unknown",
};

export const CATEGORY_COLORS: Record<FailureCategory, string> = {
  persistent_obstacle: "#f59e0b",
  localization_failure: "#a78bfa",
  controller_oscillation: "#38bdf8",
  sensor_dropout: "#fb7185",
  unknown: "#8d99a8",
};

export type EventCategory =
  | "task"
  | "planner"
  | "motion"
  | "perception"
  | "alerts";

export const EVENT_CATEGORY_OF: Record<EventType, EventCategory> = {
  task_started: "task",
  nav_goal_issued: "task",
  task_timed_out: "task",
  task_failed: "task",
  planner_state_changed: "planner",
  recovery_started: "planner",
  recovery_completed: "planner",
  velocity_command: "motion",
  pose_updated: "motion",
  obstacle_distance_updated: "perception",
  warning_raised: "alerts",
  error_raised: "alerts",
};

export const EVENT_CATEGORY_LABELS: Record<EventCategory, string> = {
  task: "Task",
  planner: "Planner",
  motion: "Motion",
  perception: "Perception",
  alerts: "Warnings & errors",
};

export const EVENT_CATEGORY_COLORS: Record<EventCategory, string> = {
  task: "#f59e0b",
  planner: "#a78bfa",
  motion: "#34d399",
  perception: "#38bdf8",
  alerts: "#fb7185",
};

export function confidencePct(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return "—";
  return `${Math.round(confidence * 100)}%`;
}

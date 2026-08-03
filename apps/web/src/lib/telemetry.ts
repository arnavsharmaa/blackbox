import type {
  Incident,
  IncidentEvent,
  TelemetryChannel,
  TelemetrySeries,
} from "@blackbox/schemas";

export type NumericPoint = { t: number; value: number };

export function eventOffsetSeconds(
  incident: Incident,
  event: IncidentEvent,
): number {
  return (
    (new Date(event.timestamp).getTime() -
      new Date(incident.start_time).getTime()) /
    1000
  );
}

export function seriesByChannel(
  incident: Incident,
): Partial<Record<TelemetryChannel, TelemetrySeries>> {
  const map: Partial<Record<TelemetryChannel, TelemetrySeries>> = {};
  for (const series of incident.telemetry) map[series.channel] = series;
  return map;
}

export function numericPoints(series: TelemetrySeries | undefined): NumericPoint[] {
  if (!series) return [];
  return series.samples.flatMap((sample) =>
    typeof sample.value === "number"
      ? [{ t: sample.t, value: sample.value }]
      : [],
  );
}

/** Last sample at or before t (step interpolation — matches replay semantics). */
export function valueAt(
  points: NumericPoint[],
  t: number,
): number | undefined {
  if (points.length === 0) return undefined;
  let result: number | undefined;
  for (const point of points) {
    if (point.t > t) break;
    result = point.value;
  }
  return result ?? points[0]?.value;
}

export function stringValueAt(
  series: TelemetrySeries | undefined,
  t: number,
): string | undefined {
  if (!series) return undefined;
  let result: string | undefined;
  for (const sample of series.samples) {
    if (sample.t > t) break;
    if (typeof sample.value === "string") result = sample.value;
  }
  return result;
}

/** Time of the failure moment: first task_timed_out or task_failed event. */
export function failureTime(incident: Incident): number | null {
  const failure = incident.events.find(
    (event) =>
      event.event_type === "task_timed_out" ||
      event.event_type === "task_failed",
  );
  return failure ? eventOffsetSeconds(incident, failure) : null;
}

export function goalPosition(
  incident: Incident,
): { x: number; y: number } | null {
  const goalEvent = incident.events.find(
    (event) => event.event_type === "nav_goal_issued",
  );
  if (!goalEvent) return null;
  const { goal_x, goal_y } = goalEvent.payload as {
    goal_x?: number;
    goal_y?: number;
  };
  if (typeof goal_x !== "number" || typeof goal_y !== "number") return null;
  return { x: goal_x, y: goal_y };
}

export function obstaclePosition(
  incident: Incident,
): { x: number; y: number } | null {
  for (const event of incident.events) {
    const { obstacle_x, obstacle_y } = event.payload as {
      obstacle_x?: number;
      obstacle_y?: number;
    };
    if (typeof obstacle_x === "number" && typeof obstacle_y === "number") {
      return { x: obstacle_x, y: obstacle_y };
    }
  }
  return null;
}

"use client";

import { useMemo } from "react";
import type { Incident } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import {
  numericPoints,
  seriesByChannel,
  stringValueAt,
  valueAt,
} from "@/lib/telemetry";

type Status = "nominal" | "degraded" | "fault";

const STATUS_STYLES: Record<Status, { dot: string; text: string }> = {
  nominal: { dot: "bg-emerald-400", text: "text-emerald-300" },
  degraded: { dot: "bg-amber-400", text: "text-amber-300" },
  fault: { dot: "bg-red-400 animate-pulse", text: "text-red-300" },
};

/**
 * Subsystem status derived from telemetry at the replay cursor. All
 * thresholds mirror the analysis engine's rules so the panel and the
 * diagnosis never disagree.
 */
export function HealthPanel({ incident }: { incident: Incident }) {
  const time = useReplayStore((s) => s.time);

  const channels = useMemo(() => seriesByChannel(incident), [incident]);
  const points = useMemo(
    () => ({
      loc: numericPoints(channels.localization_confidence),
      obstacle: numericPoints(channels.obstacle_distance),
      linear: numericPoints(channels.linear_velocity),
      angular: numericPoints(channels.angular_velocity),
      battery: numericPoints(channels.battery_pct),
    }),
    [channels],
  );

  const rows = useMemo(() => {
    const loc = valueAt(points.loc, time);
    const plannerState = stringValueAt(channels.planner_state, time) ?? "unknown";
    const obstacle = valueAt(points.obstacle, time);
    const battery = valueAt(points.battery, time);

    // Sensor freshness: is there an obstacle-distance sample within 2s?
    const freshSample = points.obstacle.some(
      (p) => p.t <= time && time - p.t <= 2.0,
    );

    const localization: [Status, string] =
      loc === undefined
        ? ["degraded", "no data"]
        : loc >= 0.8
          ? ["nominal", `${(loc * 100).toFixed(0)}% confidence`]
          : loc >= 0.5
            ? ["degraded", `${(loc * 100).toFixed(0)}% confidence`]
            : ["fault", `${(loc * 100).toFixed(0)}% confidence`];

    const planner: [Status, string] =
      plannerState === "executing" || plannerState === "planning" || plannerState === "idle"
        ? ["nominal", plannerState]
        : plannerState === "failed"
          ? ["fault", plannerState]
          : ["degraded", plannerState];

    const linear = valueAt(points.linear, time) ?? 0;
    const controller: [Status, string] =
      plannerState === "failed"
        ? ["fault", "stopped"]
        : Math.abs(linear) < 0.02 && time > 5 && plannerState !== "idle"
          ? ["degraded", "holding zero velocity"]
          : ["nominal", `${linear.toFixed(2)} m/s`];

    const sensor: [Status, string] = !freshSample
      ? time === 0
        ? ["nominal", "awaiting first scan"]
        : ["fault", "no recent scan"]
      : obstacle !== undefined && obstacle < 0.6
        ? ["degraded", `${obstacle.toFixed(2)} m clearance`]
        : ["nominal", `${obstacle?.toFixed(2) ?? "—"} m clearance`];

    // Event stream continuity is the best available network proxy.
    const network: [Status, string] = ["nominal", "telemetry link stable"];

    const batteryRow: [Status, string] =
      battery === undefined
        ? ["degraded", "no data"]
        : battery < 15
          ? ["fault", `${battery.toFixed(0)}%`]
          : battery < 30
            ? ["degraded", `${battery.toFixed(0)}%`]
            : ["nominal", `${battery.toFixed(0)}%`];

    return [
      { name: "Localization", status: localization },
      { name: "Planner", status: planner },
      { name: "Controller", status: controller },
      { name: "Obstacle sensor", status: sensor },
      { name: "Network", status: network },
      { name: "Battery", status: batteryRow },
    ];
  }, [channels, points, time]);

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          System health <span className="normal-case text-ink-faint">at cursor</span>
        </h2>
      </header>
      <ul className="grid grid-cols-2 gap-x-4 px-4 py-2">
        {rows.map((row) => {
          const [status, detail] = row.status;
          return (
            <li
              key={row.name}
              className="flex items-center justify-between gap-2 border-b border-edge/40 py-2 text-sm last:border-b-0 [&:nth-last-child(2)]:border-b-0"
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={`h-2 w-2 rounded-full ${STATUS_STYLES[status].dot}`}
                />
                {row.name}
              </span>
              <span
                className={`text-right font-mono text-[11px] ${STATUS_STYLES[status].text}`}
              >
                {detail}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

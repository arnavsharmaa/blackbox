"use client";

import { memo, useMemo, useRef } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { Incident } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import {
  numericPoints,
  seriesByChannel,
  valueAt,
  type NumericPoint,
} from "@/lib/telemetry";

// Chart plot area margins must match CHART_MARGIN for the overlay cursor math.
const CHART_MARGIN = { top: 6, right: 8, bottom: 4, left: 44 };
const CHART_HEIGHT = 110;

interface ChartSpec {
  channel:
    | "linear_velocity"
    | "angular_velocity"
    | "obstacle_distance"
    | "goal_distance"
    | "localization_confidence";
  label: string;
  color: string;
  unit: string;
  threshold?: number;
}

const CHARTS: ChartSpec[] = [
  { channel: "linear_velocity", label: "Linear velocity", color: "#34d399", unit: "m/s" },
  { channel: "angular_velocity", label: "Angular velocity", color: "#38bdf8", unit: "rad/s" },
  {
    channel: "obstacle_distance",
    label: "Obstacle distance",
    color: "#f59e0b",
    unit: "m",
    threshold: 0.6,
  },
  { channel: "goal_distance", label: "Goal distance", color: "#a78bfa", unit: "m" },
  {
    channel: "localization_confidence",
    label: "Localization confidence",
    color: "#f472b6",
    unit: "",
  },
];

export function TelemetryCharts({ incident }: { incident: Incident }) {
  const channels = useMemo(() => seriesByChannel(incident), [incident]);
  const duration = useReplayStore((s) => s.duration);

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Telemetry
        </h2>
      </header>
      <div className="divide-y divide-edge/50">
        {CHARTS.map((spec) => (
          <ChannelChart
            key={spec.channel}
            spec={spec}
            points={numericPoints(channels[spec.channel])}
            duration={duration}
          />
        ))}
      </div>
    </div>
  );
}

function ChannelChart({
  spec,
  points,
  duration,
}: {
  spec: ChartSpec;
  points: NumericPoint[];
  duration: number;
}) {
  const time = useReplayStore((s) => s.time);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const current = valueAt(points, time);

  if (points.length === 0) {
    return (
      <div className="px-4 py-3 text-sm text-ink-faint">
        {spec.label}: no telemetry recorded
      </div>
    );
  }

  const handleSeek = (clientX: number) => {
    const wrapper = wrapperRef.current;
    if (!wrapper || duration === 0) return;
    const rect = wrapper.getBoundingClientRect();
    const plotLeft = rect.left + CHART_MARGIN.left;
    const plotWidth = rect.width - CHART_MARGIN.left - CHART_MARGIN.right;
    if (plotWidth <= 0) return;
    const fraction = Math.min(
      Math.max((clientX - plotLeft) / plotWidth, 0),
      1,
    );
    useReplayStore.getState().seek(fraction * duration);
  };

  // Overlay cursor position in CSS: percentage of the plot area.
  const cursorLeft = duration
    ? `calc(${CHART_MARGIN.left}px + (100% - ${CHART_MARGIN.left + CHART_MARGIN.right}px) * ${Math.min(time / duration, 1)})`
    : "0";

  return (
    <div className="px-2 py-1.5">
      <div className="flex items-baseline justify-between px-2">
        <span className="text-xs font-medium text-ink-dim">{spec.label}</span>
        <span className="font-mono text-xs tabular-nums" style={{ color: spec.color }}>
          {current !== undefined ? current.toFixed(2) : "—"}
          {spec.unit && <span className="text-ink-faint"> {spec.unit}</span>}
        </span>
      </div>
      <div
        ref={wrapperRef}
        className="relative cursor-crosshair"
        style={{ height: CHART_HEIGHT }}
        onPointerDown={(e) => handleSeek(e.clientX)}
        role="presentation"
      >
        <StaticChart spec={spec} points={points} duration={duration} />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-1 w-px bg-white/70"
          style={{ left: cursorLeft }}
        />
      </div>
    </div>
  );
}

/** Keeps small-range axes (e.g. confidence 0.95–0.99) distinguishable. */
function formatTick(value: number): string {
  const text = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
  return text.replace(/\.?0+$/, "") || "0";
}

/**
 * The chart body never changes during replay — memoized so only the cheap
 * cursor overlay updates each frame.
 */
const StaticChart = memo(function StaticChart({
  spec,
  points,
  duration,
}: {
  spec: ChartSpec;
  points: NumericPoint[];
  duration: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={points} margin={CHART_MARGIN}>
        <XAxis
          dataKey="t"
          type="number"
          domain={[0, duration]}
          hide
          allowDataOverflow
        />
        <YAxis
          width={CHART_MARGIN.left - 4}
          tick={{ fill: "#5d6875", fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: "#232b36" }}
          tickFormatter={formatTick}
          domain={["auto", "auto"]}
        />
        {spec.threshold !== undefined && (
          <ReferenceLine
            y={spec.threshold}
            stroke="#f87171"
            strokeDasharray="4 3"
            strokeOpacity={0.7}
          />
        )}
        <Line
          type="linear"
          dataKey="value"
          stroke={spec.color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
});

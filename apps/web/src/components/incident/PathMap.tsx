"use client";

import { useMemo } from "react";
import type { Incident } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import {
  goalPosition,
  numericPoints,
  obstaclePosition,
  seriesByChannel,
  valueAt,
} from "@/lib/telemetry";

const VIEW_W = 420;
const VIEW_H = 300;
const PAD = 30;

export function PathMap({ incident }: { incident: Incident }) {
  const time = useReplayStore((s) => s.time);

  const geometry = useMemo(() => {
    const channels = seriesByChannel(incident);
    const xs = numericPoints(channels.pos_x);
    const ys = numericPoints(channels.pos_y);
    const hs = numericPoints(channels.heading);
    const goal = goalPosition(incident);
    const obstacle = obstaclePosition(incident);

    const allX = xs.map((p) => p.value).concat(goal ? [goal.x] : [], obstacle ? [obstacle.x] : []);
    const allY = ys.map((p) => p.value).concat(goal ? [goal.y] : [], obstacle ? [obstacle.y] : []);
    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const scale = Math.min(
      (VIEW_W - PAD * 2) / spanX,
      (VIEW_H - PAD * 2) / spanY,
    );
    const offsetX = (VIEW_W - spanX * scale) / 2;
    const offsetY = (VIEW_H - spanY * scale) / 2;

    // World -> SVG (y axis flipped so +y is up, matching floor plans).
    const toSvg = (x: number, y: number): [number, number] => [
      offsetX + (x - minX) * scale,
      VIEW_H - offsetY - (y - minY) * scale,
    ];

    const path = xs
      .map((p, i) => {
        const y = ys[i]?.value ?? 0;
        const [sx, sy] = toSvg(p.value, y);
        return `${i === 0 ? "M" : "L"}${sx.toFixed(1)},${sy.toFixed(1)}`;
      })
      .join(" ");

    const first: [number, number] | null =
      xs.length > 0 && ys.length > 0
        ? toSvg(xs[0]!.value, ys[0]!.value)
        : null;
    const last: [number, number] | null =
      xs.length > 0 && ys.length > 0
        ? toSvg(xs[xs.length - 1]!.value, ys[ys.length - 1]!.value)
        : null;

    return { xs, ys, hs, goal, obstacle, toSvg, path, first, last, scale };
  }, [incident]);

  if (geometry.xs.length === 0) {
    return (
      <div className="rounded-lg border border-edge bg-surface-1 p-4 text-sm text-ink-faint">
        No position telemetry recorded for this incident.
      </div>
    );
  }

  const robotX = valueAt(geometry.xs, time);
  const robotY = valueAt(geometry.ys, time);
  const robotH = valueAt(geometry.hs, time) ?? 0;
  const robot =
    robotX !== undefined && robotY !== undefined
      ? geometry.toSvg(robotX, robotY)
      : null;

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Robot path
        </h2>
        <span className="font-mono text-xs text-ink-faint">
          {robotX !== undefined && robotY !== undefined
            ? `(${robotX.toFixed(2)}, ${robotY.toFixed(2)}) m`
            : ""}
        </span>
      </header>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="block w-full"
        role="img"
        aria-label="Map of the robot path with start, goal, obstacle and current position"
      >
        {/* Grid */}
        <defs>
          <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path
              d="M 24 0 L 0 0 0 24"
              fill="none"
              stroke="#1b222c"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width={VIEW_W} height={VIEW_H} fill="url(#grid)" />

        {/* Full path (dim) */}
        <path
          d={geometry.path}
          fill="none"
          stroke="#334050"
          strokeWidth={2}
          strokeDasharray="3 3"
        />
        {/* Traveled path */}
        <TraveledPath geometry={geometry} time={time} />

        {/* Goal */}
        {geometry.goal && (
          <MapMarker
            pos={geometry.toSvg(geometry.goal.x, geometry.goal.y)}
            label="GOAL"
            color="#34d399"
            shape="target"
          />
        )}

        {/* Obstacle */}
        {geometry.obstacle && (
          <MapMarker
            pos={geometry.toSvg(geometry.obstacle.x, geometry.obstacle.y)}
            label="OBSTACLE"
            color="#f87171"
            shape="cross"
          />
        )}

        {/* Start */}
        {geometry.first && (
          <MapMarker pos={geometry.first} label="START" color="#38bdf8" shape="ring" />
        )}

        {/* Final position */}
        {geometry.last && (
          <circle
            cx={geometry.last[0]}
            cy={geometry.last[1]}
            r={4}
            fill="none"
            stroke="#8d99a8"
            strokeWidth={1.5}
            strokeDasharray="2 2"
          />
        )}

        {/* Robot marker */}
        {robot && (
          <g transform={`translate(${robot[0]}, ${robot[1]}) rotate(${(-robotH * 180) / Math.PI})`}>
            <circle r={7} fill="rgba(245,158,11,0.25)" />
            <polygon points="7,0 -4,4.5 -4,-4.5" fill="#f59e0b" />
          </g>
        )}
      </svg>
      <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-edge px-4 py-2 text-[11px] text-ink-faint">
        <LegendSwatch color="#38bdf8" label="Start" />
        <LegendSwatch color="#34d399" label="Goal" />
        <LegendSwatch color="#f87171" label="Obstacle" />
        <LegendSwatch color="#f59e0b" label="Robot" />
        <LegendSwatch color="#8d99a8" label="Final position" />
      </div>
    </div>
  );
}

function TraveledPath({
  geometry,
  time,
}: {
  geometry: {
    xs: { t: number; value: number }[];
    ys: { t: number; value: number }[];
    toSvg: (x: number, y: number) => [number, number];
  };
  time: number;
}) {
  const d = useMemo(() => {
    const segments: string[] = [];
    for (let i = 0; i < geometry.xs.length; i++) {
      const px = geometry.xs[i];
      const py = geometry.ys[i];
      if (!px || !py || px.t > time) break;
      const [sx, sy] = geometry.toSvg(px.value, py.value);
      segments.push(`${segments.length === 0 ? "M" : "L"}${sx.toFixed(1)},${sy.toFixed(1)}`);
    }
    return segments.join(" ");
  }, [geometry, time]);
  return (
    <path d={d} fill="none" stroke="#f59e0b" strokeWidth={2.5} strokeLinecap="round" />
  );
}

function MapMarker({
  pos,
  label,
  color,
  shape,
}: {
  pos: [number, number];
  label: string;
  color: string;
  shape: "target" | "cross" | "ring";
}) {
  const [x, y] = pos;
  return (
    <g>
      {shape === "target" && (
        <>
          <circle cx={x} cy={y} r={8} fill="none" stroke={color} strokeWidth={1.5} />
          <circle cx={x} cy={y} r={2.5} fill={color} />
        </>
      )}
      {shape === "cross" && (
        <path
          d={`M${x - 5},${y - 5} L${x + 5},${y + 5} M${x - 5},${y + 5} L${x + 5},${y - 5}`}
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
        />
      )}
      {shape === "ring" && (
        <circle cx={x} cy={y} r={5} fill="none" stroke={color} strokeWidth={2} />
      )}
      <text
        x={x}
        y={y - 11}
        textAnchor="middle"
        fill={color}
        fontSize={9}
        fontFamily="var(--font-mono)"
        fontWeight={600}
      >
        {label}
      </text>
    </g>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: color }}
      />
      {label}
    </span>
  );
}

"use client";

import { useMemo, useRef } from "react";
import type { Incident } from "@blackbox/schemas";
import { useReplayStore } from "@/store/replay";
import { eventOffsetSeconds } from "@/lib/telemetry";
import {
  EVENT_CATEGORY_COLORS,
  EVENT_CATEGORY_LABELS,
  EVENT_CATEGORY_OF,
  type EventCategory,
} from "@/lib/format";

const LANES: EventCategory[] = [
  "task",
  "planner",
  "perception",
  "motion",
  "alerts",
];

interface TimelineEvent {
  index: number;
  t: number;
  category: EventCategory;
  severity: string;
  message: string;
  type: string;
}

export function Timeline({ incident }: { incident: Incident }) {
  const duration = useReplayStore((s) => s.duration);
  const time = useReplayStore((s) => s.time);
  const failureT = useReplayStore((s) => s.failureT);
  const selectedEvent = useReplayStore((s) => s.selectedEvent);
  const visibleCategories = useReplayStore((s) => s.visibleCategories);
  const trackRef = useRef<HTMLDivElement>(null);

  const events = useMemo<TimelineEvent[]>(
    () =>
      incident.events.map((event, index) => ({
        index,
        t: eventOffsetSeconds(incident, event),
        category: EVENT_CATEGORY_OF[event.event_type],
        severity: event.severity,
        message: event.message,
        type: event.event_type,
      })),
    [incident],
  );

  // The first 6rem (96px) of the track is the lane-label gutter.
  const GUTTER_PX = 96;
  const seekFromPointer = (clientX: number) => {
    const track = trackRef.current;
    if (!track || duration === 0) return;
    const rect = track.getBoundingClientRect();
    const usable = rect.width - GUTTER_PX;
    if (usable <= 0) return;
    const fraction = Math.min(
      Math.max((clientX - rect.left - GUTTER_PX) / usable, 0),
      1,
    );
    useReplayStore.getState().seek(fraction * duration);
  };

  const pct = (t: number) => `${duration ? (t / duration) * 100 : 0}%`;

  return (
    <div className="rounded-lg border border-edge bg-surface-1">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-edge px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-dim">
          Timeline
        </h2>
        <div
          className="flex flex-wrap gap-1.5"
          role="group"
          aria-label="Filter event categories"
        >
          {LANES.map((category) => {
            const active = visibleCategories.includes(category);
            return (
              <button
                key={category}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  useReplayStore.getState().toggleCategory(category)
                }
                className={`flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] ${
                  active
                    ? "border-edge-strong bg-surface-2 text-ink"
                    : "border-edge text-ink-faint"
                }`}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: active
                      ? EVENT_CATEGORY_COLORS[category]
                      : "var(--color-ink-faint)",
                  }}
                />
                {EVENT_CATEGORY_LABELS[category]}
              </button>
            );
          })}
        </div>
      </header>

      <div className="px-4 py-3">
        <div
          ref={trackRef}
          className="relative cursor-crosshair select-none"
          onPointerDown={(e) => {
            // Event markers handle their own clicks; empty track area seeks.
            if (!(e.target as HTMLElement).closest("button")) {
              seekFromPointer(e.clientX);
            }
          }}
          role="slider"
          aria-label="Timeline scrubber"
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          aria-valuenow={Math.round(time)}
          tabIndex={0}
          onKeyDown={(e) => {
            const store = useReplayStore.getState();
            if (e.key === "ArrowRight") store.seek(store.time + 1);
            if (e.key === "ArrowLeft") store.seek(store.time - 1);
          }}
        >
          {/* Lanes */}
          {LANES.map((category) => (
            <div
              key={category}
              className="relative flex h-8 items-center border-b border-edge/40 last:border-b-0"
            >
              <span className="pointer-events-none absolute left-0 z-10 w-20 pr-2 text-right text-[10px] uppercase tracking-wide text-ink-faint">
                {EVENT_CATEGORY_LABELS[category]}
              </span>
              <div className="relative ml-24 h-full flex-1">
                {visibleCategories.includes(category) &&
                  events
                    .filter((event) => event.category === category)
                    .map((event) => (
                      <button
                        key={event.index}
                        type="button"
                        title={`t=${event.t.toFixed(1)}s — ${event.message}`}
                        aria-label={`Event at ${event.t.toFixed(1)} seconds: ${event.message}`}
                        onClick={() =>
                          useReplayStore
                            .getState()
                            .selectEvent(event.index, event.t)
                        }
                        className={`absolute top-1/2 h-3.5 w-[5px] -translate-x-1/2 -translate-y-1/2 rounded-[2px] transition-transform hover:scale-y-150 ${
                          selectedEvent === event.index
                            ? "z-20 scale-y-[1.7] ring-2 ring-white/70"
                            : ""
                        }`}
                        style={{
                          left: pct(event.t),
                          background:
                            event.severity === "critical" ||
                            event.severity === "error"
                              ? "#f87171"
                              : EVENT_CATEGORY_COLORS[category],
                        }}
                      />
                    ))}
              </div>
            </div>
          ))}

          {/* Overlay: failure marker + replay cursor, aligned to the lane area */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 left-24 right-0 z-30"
          >
            {failureT !== null && (
              <div
                className="absolute inset-y-0 w-px border-l border-dashed border-red-400/80"
                style={{ left: pct(failureT) }}
              />
            )}
            <div
              className="absolute inset-y-0 w-px bg-accent shadow-[0_0_6px_rgba(245,158,11,0.8)]"
              style={{ left: pct(time) }}
            />
          </div>
        </div>

        {/* Axis */}
        <div className="relative ml-24 mt-1 h-4 text-[10px] tabular-nums text-ink-faint">
          {axisTicks(duration).map((tick) => (
            <span
              key={tick}
              className="absolute -translate-x-1/2"
              style={{ left: pct(tick) }}
            >
              {tick}s
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function axisTicks(duration: number): number[] {
  if (duration <= 0) return [];
  const step = duration > 120 ? 30 : duration > 60 ? 15 : 10;
  const ticks: number[] = [];
  for (let t = 0; t <= duration; t += step) ticks.push(t);
  return ticks;
}

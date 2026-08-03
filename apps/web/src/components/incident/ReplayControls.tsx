"use client";

import { useEffect } from "react";
import { REPLAY_SPEEDS, useReplayStore } from "@/store/replay";
import { formatClock } from "@/lib/format";

export function ReplayControls() {
  const time = useReplayStore((s) => s.time);
  const duration = useReplayStore((s) => s.duration);
  const playing = useReplayStore((s) => s.playing);
  const speed = useReplayStore((s) => s.speed);
  const failureT = useReplayStore((s) => s.failureT);
  const pauseAtFailure = useReplayStore((s) => s.pauseAtFailure);

  // Space toggles play/pause unless a form control is focused.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || tag === "BUTTON")
        return;
      if (event.code === "Space") {
        event.preventDefault();
        useReplayStore.getState().togglePlay();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const store = useReplayStore.getState;
  const buttonClass =
    "rounded border border-edge-strong bg-surface-2 px-2.5 py-1.5 text-sm " +
    "hover:border-accent disabled:opacity-40 disabled:hover:border-edge-strong";

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-edge bg-surface-1 px-4 py-3">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => store().togglePlay()}
          className={`${buttonClass} min-w-[76px] font-medium`}
          aria-label={playing ? "Pause replay" : "Play replay"}
        >
          {playing ? "❚❚ Pause" : "▶ Play"}
        </button>
        <button
          type="button"
          onClick={() => store().reset()}
          className={buttonClass}
          aria-label="Reset replay to start"
        >
          ⟲ Reset
        </button>
        <button
          type="button"
          onClick={() => store().jumpToFailure()}
          disabled={failureT === null}
          className={`${buttonClass} text-red-300`}
          aria-label="Jump to failure moment"
        >
          ⚑ Failure
        </button>
      </div>

      <div
        className="flex items-center rounded border border-edge-strong bg-surface-2 p-0.5"
        role="group"
        aria-label="Replay speed"
      >
        {REPLAY_SPEEDS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => store().setSpeed(value)}
            aria-pressed={speed === value}
            className={`rounded px-2 py-1 text-xs tabular-nums ${
              speed === value
                ? "bg-accent font-semibold text-black"
                : "text-ink-dim hover:text-ink"
            }`}
          >
            {value}×
          </button>
        ))}
      </div>

      <label className="flex items-center gap-1.5 text-xs text-ink-dim">
        <input
          type="checkbox"
          checked={pauseAtFailure}
          onChange={(e) => store().setPauseAtFailure(e.target.checked)}
          className="accent-amber-500"
        />
        Pause at failure
      </label>

      <div className="flex min-w-[220px] flex-1 items-center gap-3">
        <input
          type="range"
          min={0}
          max={duration}
          step={0.1}
          value={time}
          onChange={(e) => store().seek(Number(e.target.value))}
          className="h-1.5 flex-1 cursor-pointer accent-amber-500"
          aria-label="Replay position"
        />
        <span className="font-mono text-sm tabular-nums text-ink">
          {formatClock(time)}
          <span className="text-ink-faint"> / {formatClock(duration)}</span>
        </span>
      </div>
    </div>
  );
}

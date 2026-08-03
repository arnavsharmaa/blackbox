"use client";

import { useEffect } from "react";
import { useReplayStore } from "@/store/replay";

/**
 * Drives the replay clock with requestAnimationFrame while playing.
 * Mount exactly once per incident-detail page.
 */
export function useReplayClock(): void {
  const playing = useReplayStore((state) => state.playing);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      useReplayStore.getState().tick(dt);
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [playing]);
}

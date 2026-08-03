"use client";

import { create } from "zustand";
import type { EventCategory } from "@/lib/format";

export const REPLAY_SPEEDS = [0.5, 1, 2, 4] as const;
export type ReplaySpeed = (typeof REPLAY_SPEEDS)[number];

const ALL_CATEGORIES: EventCategory[] = [
  "task",
  "planner",
  "motion",
  "perception",
  "alerts",
];

interface ReplayState {
  duration: number;
  failureT: number | null;
  time: number;
  playing: boolean;
  speed: ReplaySpeed;
  pauseAtFailure: boolean;
  /** Index into the incident's event array, or null. */
  selectedEvent: number | null;
  visibleCategories: EventCategory[];

  init: (duration: number, failureT: number | null) => void;
  seek: (t: number) => void;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (speed: ReplaySpeed) => void;
  reset: () => void;
  jumpToFailure: () => void;
  setPauseAtFailure: (value: boolean) => void;
  selectEvent: (index: number | null, t?: number) => void;
  toggleCategory: (category: EventCategory) => void;
  /** Advance by wall-clock dt (seconds); returns whether still playing. */
  tick: (dt: number) => void;
}

export const useReplayStore = create<ReplayState>((set, get) => ({
  duration: 0,
  failureT: null,
  time: 0,
  playing: false,
  speed: 1,
  pauseAtFailure: true,
  selectedEvent: null,
  visibleCategories: ALL_CATEGORIES,

  init: (duration, failureT) =>
    set({
      duration,
      failureT,
      time: 0,
      playing: false,
      speed: 1,
      selectedEvent: null,
      pauseAtFailure: true,
      visibleCategories: ALL_CATEGORIES,
    }),

  seek: (t) =>
    set((state) => ({
      time: Math.min(Math.max(t, 0), state.duration),
    })),

  play: () =>
    set((state) => {
      // Restart from the beginning when play is pressed at the end.
      if (state.time >= state.duration - 1e-6) {
        return { playing: true, time: 0 };
      }
      return { playing: true };
    }),
  pause: () => set({ playing: false }),
  togglePlay: () => {
    const { playing, play, pause } = get();
    if (playing) pause();
    else play();
  },
  setSpeed: (speed) => set({ speed }),
  reset: () => set({ time: 0, playing: false, selectedEvent: null }),

  jumpToFailure: () => {
    const { failureT, duration } = get();
    set({ time: failureT ?? duration, playing: false });
  },
  setPauseAtFailure: (value) => set({ pauseAtFailure: value }),

  selectEvent: (index, t) =>
    set((state) => ({
      selectedEvent: index,
      time: t !== undefined ? Math.min(Math.max(t, 0), state.duration) : state.time,
    })),

  toggleCategory: (category) =>
    set((state) => ({
      visibleCategories: state.visibleCategories.includes(category)
        ? state.visibleCategories.filter((c) => c !== category)
        : [...state.visibleCategories, category],
    })),

  tick: (dt) => {
    const state = get();
    if (!state.playing) return;
    const next = state.time + dt * state.speed;

    // Pause exactly at the failure moment when crossing it.
    if (
      state.pauseAtFailure &&
      state.failureT !== null &&
      state.time < state.failureT &&
      next >= state.failureT
    ) {
      set({ time: state.failureT, playing: false });
      return;
    }
    if (next >= state.duration) {
      set({ time: state.duration, playing: false });
      return;
    }
    set({ time: next });
  },
}));

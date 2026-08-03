import { beforeEach, describe, expect, it } from "vitest";
import { useReplayStore } from "@/store/replay";

describe("replay store", () => {
  beforeEach(() => {
    useReplayStore.getState().init(90, 80);
  });

  it("initializes with defaults", () => {
    const state = useReplayStore.getState();
    expect(state.duration).toBe(90);
    expect(state.failureT).toBe(80);
    expect(state.time).toBe(0);
    expect(state.playing).toBe(false);
    expect(state.speed).toBe(1);
  });

  it("seek clamps to [0, duration]", () => {
    const store = useReplayStore.getState();
    store.seek(120);
    expect(useReplayStore.getState().time).toBe(90);
    store.seek(-5);
    expect(useReplayStore.getState().time).toBe(0);
  });

  it("tick advances time by dt * speed", () => {
    const store = useReplayStore.getState();
    store.play();
    store.setSpeed(2);
    useReplayStore.getState().tick(1.5);
    expect(useReplayStore.getState().time).toBeCloseTo(3.0);
  });

  it("does not advance while paused", () => {
    useReplayStore.getState().tick(5);
    expect(useReplayStore.getState().time).toBe(0);
  });

  it("pauses exactly at the failure moment when enabled", () => {
    const store = useReplayStore.getState();
    store.seek(79);
    store.play();
    store.setSpeed(4);
    useReplayStore.getState().tick(1); // would jump to 83, must stop at 80
    const state = useReplayStore.getState();
    expect(state.time).toBe(80);
    expect(state.playing).toBe(false);
  });

  it("runs through the failure moment when pauseAtFailure is off", () => {
    const store = useReplayStore.getState();
    store.setPauseAtFailure(false);
    store.seek(79);
    store.play();
    store.setSpeed(4);
    useReplayStore.getState().tick(1);
    expect(useReplayStore.getState().time).toBeCloseTo(83);
    expect(useReplayStore.getState().playing).toBe(true);
  });

  it("stops at the end of the incident", () => {
    const store = useReplayStore.getState();
    store.setPauseAtFailure(false);
    store.seek(89);
    store.play();
    useReplayStore.getState().tick(5);
    const state = useReplayStore.getState();
    expect(state.time).toBe(90);
    expect(state.playing).toBe(false);
  });

  it("play from the end restarts at zero", () => {
    const store = useReplayStore.getState();
    store.seek(90);
    store.play();
    expect(useReplayStore.getState().time).toBe(0);
    expect(useReplayStore.getState().playing).toBe(true);
  });

  it("jumpToFailure seeks to the failure timestamp and pauses", () => {
    const store = useReplayStore.getState();
    store.play();
    store.jumpToFailure();
    const state = useReplayStore.getState();
    expect(state.time).toBe(80);
    expect(state.playing).toBe(false);
  });

  it("selectEvent stores the index and can move the cursor", () => {
    useReplayStore.getState().selectEvent(3, 42);
    const state = useReplayStore.getState();
    expect(state.selectedEvent).toBe(3);
    expect(state.time).toBe(42);
  });

  it("toggleCategory hides and shows event categories", () => {
    const store = useReplayStore.getState();
    store.toggleCategory("motion");
    expect(useReplayStore.getState().visibleCategories).not.toContain("motion");
    useReplayStore.getState().toggleCategory("motion");
    expect(useReplayStore.getState().visibleCategories).toContain("motion");
  });
});

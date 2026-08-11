import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IncidentHeader } from "@/components/incident/IncidentHeader";
import { Timeline } from "@/components/incident/Timeline";
import { EvidencePanel } from "@/components/incident/EvidencePanel";
import { ReplayControls } from "@/components/incident/ReplayControls";
import { EventInspector } from "@/components/incident/EventInspector";
import { useReplayStore } from "@/store/replay";
import { testAnalysis, testIncident } from "./fixtures";

const pushSpy = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushSpy }),
}));

beforeEach(() => {
  useReplayStore.getState().init(60, 50);
  pushSpy.mockClear();
});

describe("Timeline", () => {
  it("renders event markers and selects one on click", async () => {
    const user = userEvent.setup();
    render(<Timeline incident={testIncident} />);

    const marker = screen.getByRole("button", {
      name: /Obstacle below safety threshold/,
    });
    await user.click(marker);

    const state = useReplayStore.getState();
    expect(state.selectedEvent).toBe(2);
    expect(state.time).toBeCloseTo(20);
  });

  it("hides a lane's markers when its category filter is toggled off", async () => {
    const user = userEvent.setup();
    render(<Timeline incident={testIncident} />);

    expect(
      screen.getByRole("button", { name: /Obstacle below safety threshold/ }),
    ).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Warnings & errors" }),
    );
    expect(
      screen.queryByRole("button", { name: /Obstacle below safety threshold/ }),
    ).toBeNull();
  });
});

describe("EvidencePanel", () => {
  it("lists evidence and seeks to the item's timestamp on click", async () => {
    const user = userEvent.setup();
    render(<EvidencePanel analysis={testAnalysis} />);

    expect(screen.getByText("2 items")).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: /Task timed out at t=50.0 s/ }),
    );
    expect(useReplayStore.getState().time).toBe(50);
  });
});

describe("ReplayControls", () => {
  it("play/pause toggles the store", async () => {
    const user = userEvent.setup();
    render(<ReplayControls />);

    await user.click(screen.getByRole("button", { name: "Play replay" }));
    expect(useReplayStore.getState().playing).toBe(true);
    await user.click(screen.getByRole("button", { name: "Pause replay" }));
    expect(useReplayStore.getState().playing).toBe(false);
  });

  it("changes speed and jumps to failure", async () => {
    const user = userEvent.setup();
    render(<ReplayControls />);

    await user.click(screen.getByRole("button", { name: "4×" }));
    expect(useReplayStore.getState().speed).toBe(4);

    await user.click(
      screen.getByRole("button", { name: "Jump to failure moment" }),
    );
    expect(useReplayStore.getState().time).toBe(50);
  });

  it("scrubber seeks", () => {
    render(<ReplayControls />);
    const slider = screen.getByRole("slider", { name: "Replay position" });
    fireEvent.change(slider, { target: { value: "33" } });
    expect(useReplayStore.getState().time).toBeCloseTo(33);
  });
});

describe("EventInspector", () => {
  it("prompts until an event is selected, then shows its payload", () => {
    const { rerender } = render(<EventInspector incident={testIncident} />);
    expect(
      screen.getByText(/Select an event on the timeline/),
    ).toBeTruthy();

    useReplayStore.getState().selectEvent(2, 20);
    rerender(<EventInspector incident={testIncident} />);
    expect(screen.getByText("Obstacle below safety threshold")).toBeTruthy();
    expect(screen.getByText(/"distance_m": 0.5/)).toBeTruthy();
  });
});

describe("IncidentHeader delete", () => {
  it("confirms, calls the API, and navigates home", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn(() => true));

    const user = userEvent.setup();
    render(<IncidentHeader incident={testIncident} analysis={testAnalysis} />);
    await user.click(screen.getByRole("button", { name: "Delete incident" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toContain("/api/incidents/INC-TEST-100");
    expect(init.method).toBe("DELETE");
    expect(pushSpy).toHaveBeenCalledWith("/");
  });

  it("does nothing when the confirmation is declined", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn(() => false));

    const user = userEvent.setup();
    render(<IncidentHeader incident={testIncident} analysis={testAnalysis} />);
    await user.click(screen.getByRole("button", { name: "Delete incident" }));
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

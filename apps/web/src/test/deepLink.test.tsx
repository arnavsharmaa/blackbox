import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Suspense } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import IncidentDetailPage from "@/app/incidents/[id]/page";
import { ReplayControls } from "@/components/incident/ReplayControls";
import { useReplayStore } from "@/store/replay";
import { testAnalysis, testIncident } from "./fixtures";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("replay deep links", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ incident: testIncident, analysis: testAnalysis }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );
  });

  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("?t= seeks the replay after the incident loads", async () => {
    window.history.replaceState(null, "", "/incidents/INC-TEST-100?t=25");
    const params = Promise.resolve({ id: "INC-TEST-100" }) as Promise<{
      id: string;
    }> & { status: string; value: { id: string } };
    params.status = "fulfilled";
    params.value = { id: "INC-TEST-100" };

    render(
      <Suspense fallback={<div>suspended</div>}>
        <IncidentDetailPage params={params} />
      </Suspense>,
    );
    await screen.findAllByText(/Deliver pallet to Loading Bay B/);
    await waitFor(() => {
      expect(useReplayStore.getState().time).toBeCloseTo(25);
    });
  });

  it("copy-link button writes a URL with the current time", async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(window.navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    window.history.replaceState(null, "", "/incidents/INC-TEST-100");
    useReplayStore.getState().init(60, 50);
    useReplayStore.getState().seek(33);

    render(<ReplayControls />);
    fireEvent.click(
      screen.getByRole("button", { name: "Copy link to this moment" }),
    );
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining("/incidents/INC-TEST-100?t=33.0"),
      );
    });
    expect(await screen.findByText("✓ Copied")).toBeTruthy();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OverviewPage from "@/app/page";
import { listResponse, testSummaries } from "./fixtures";

function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const robot = url.searchParams.get("robot_id");
    const severity = url.searchParams.get("severity");
    let items = testSummaries;
    if (robot) items = items.filter((i) => i.robot_id === robot);
    if (severity) items = items.filter((i) => i.severity === severity);
    return new Response(JSON.stringify(listResponse(items)), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("incident overview", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch());
  });

  it("renders the incident list with analysis columns", async () => {
    render(<OverviewPage />);
    expect(
      await screen.findByText("Deliver pallet to Loading Bay B"),
    ).toBeTruthy();
    expect(screen.getByText("Return to charging dock")).toBeTruthy();
    expect(screen.getAllByText("Persistent obstacle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Localization failure").length).toBeGreaterThan(0);
    // Stat cards
    expect(screen.getByText("Total incidents")).toBeTruthy();
    expect(screen.getByText("Critical incidents")).toBeTruthy();
  });

  it("filters by robot", async () => {
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText("Deliver pallet to Loading Bay B");

    await user.selectOptions(screen.getByLabelText("Robot"), "W-087");
    await waitFor(() => {
      expect(screen.queryByText("Deliver pallet to Loading Bay B")).toBeNull();
    });
    expect(screen.getByText("Return to charging dock")).toBeTruthy();
  });

  it("shows an empty state when no incidents match", async () => {
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText("Deliver pallet to Loading Bay B");

    await user.selectOptions(screen.getByLabelText("Severity"), "info");
    expect(
      await screen.findByText("No incidents match these filters"),
    ).toBeTruthy();
  });

  it("shows an error state when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    render(<OverviewPage />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getAllByText(/Cannot reach the BlackBox API/).length)
      .toBeGreaterThan(0);
  });
});

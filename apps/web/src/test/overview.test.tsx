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
    const q = url.searchParams.get("q")?.toLowerCase();
    let items = testSummaries;
    if (robot) items = items.filter((i) => i.robot_id === robot);
    if (severity) items = items.filter((i) => i.severity === severity);
    if (q) {
      items = items.filter((i) =>
        `${i.id} ${i.task_name} ${i.summary}`.toLowerCase().includes(q),
      );
    }
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

  it("free-text search narrows the table after the debounce", async () => {
    const user = userEvent.setup();
    render(<OverviewPage />);
    await screen.findByText("Deliver pallet to Loading Bay B");

    await user.type(
      screen.getByLabelText("Search incidents"),
      "charging dock",
    );
    await waitFor(() => {
      expect(screen.queryByText("Deliver pallet to Loading Bay B")).toBeNull();
    });
    expect(screen.getByText("Return to charging dock")).toBeTruthy();

    // Clear filters resets the search box too.
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(
      (screen.getByLabelText("Search incidents") as HTMLInputElement).value,
    ).toBe("");
    expect(
      await screen.findByText("Deliver pallet to Loading Bay B"),
    ).toBeTruthy();
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

  it("pages through a large incident list", async () => {
    const base = testSummaries[0]!;
    const many = Array.from({ length: 30 }, (_, i) => ({
      ...base,
      id: `INC-PAGE-${String(i).padStart(3, "0")}`,
      task_name: `Paged task ${i}`,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        const limit = Number(url.searchParams.get("limit") ?? 50);
        const offset = Number(url.searchParams.get("offset") ?? 0);
        return new Response(
          JSON.stringify({
            items: many.slice(offset, offset + limit),
            total: many.length,
            limit,
            offset,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }),
    );

    const user = userEvent.setup();
    render(<OverviewPage />);
    expect(await screen.findByText("Showing 1–25 of 30")).toBeTruthy();
    expect(screen.getByText("Paged task 0")).toBeTruthy();
    expect(screen.queryByText("Paged task 25")).toBeNull();
    expect(
      (screen.getByRole("button", { name: "← Prev" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "Next →" }));
    expect(await screen.findByText("Showing 26–30 of 30")).toBeTruthy();
    expect(screen.getByText("Paged task 25")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Next →" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
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

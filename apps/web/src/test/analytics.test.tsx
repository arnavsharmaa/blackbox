import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { AnalyticsResponse } from "@blackbox/schemas";
import AnalyticsPage from "@/app/analytics/page";

const analytics: AnalyticsResponse = {
  total_incidents: 4,
  critical_incidents: 1,
  total_recovery_attempts: 4,
  categories: [
    { category: "persistent_obstacle", count: 1 },
    { category: "localization_failure", count: 1 },
  ],
  outcomes: [
    { outcome: "failed", count: 2 },
    { outcome: "timed_out", count: 1 },
  ],
  by_robot: [
    {
      robot_id: "W-104",
      robot_model: "Fetchbot AMR-600",
      incidents: 1,
      critical: 1,
      recovery_attempts: 3,
      top_category: "persistent_obstacle",
    },
    {
      robot_id: "W-087",
      robot_model: "Fetchbot AMR-600",
      incidents: 1,
      critical: 0,
      recovery_attempts: 1,
      top_category: "localization_failure",
    },
  ],
  by_software_version: [
    {
      software_version: "nav-stack 2.14.1",
      incidents: 4,
      categories: [{ category: "persistent_obstacle", count: 1 }],
    },
  ],
  blockage_hotspots: [
    {
      facility: "Warehouse 3 — Fremont",
      x: 13.5,
      y: 5.5,
      count: 2,
      incident_ids: ["INC-2026-0728-001", "INC-2026-0802-007"],
    },
  ],
  daily: [
    { date: "2026-07-28", category: "persistent_obstacle", count: 1 },
    { date: "2026-07-29", category: "localization_failure", count: 1 },
  ],
  calibration: [
    {
      category: "persistent_obstacle",
      reviewed: 4,
      confirmed: 3,
      precision: 0.75,
      corrected_to: [{ category: "sensor_dropout", count: 1 }],
    },
  ],
};

function stubFetch(body: AnalyticsResponse) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

describe("analytics page", () => {
  beforeEach(() => {
    stubFetch(analytics);
  });

  it("renders fleet stats, robot table, and version breakdown", async () => {
    render(<AnalyticsPage />);
    expect(await screen.findByText("Fleet analytics")).toBeTruthy();
    expect(screen.getByText("Total incidents")).toBeTruthy();
    expect(screen.getByText("W-104")).toBeTruthy();
    expect(screen.getByText("W-087")).toBeTruthy();
    expect(screen.getByText("nav-stack 2.14.1")).toBeTruthy();
    expect(
      screen.getByText("Persistent obstacle ×1", { exact: false }),
    ).toBeTruthy();
  });

  it("lists blockage hotspots with incident links", async () => {
    render(<AnalyticsPage />);
    expect(await screen.findByText(/\(13\.5, 5\.5\) m/)).toBeTruthy();
    expect(screen.getByText("×2")).toBeTruthy();
    const link = screen.getByRole("link", { name: "INC-2026-0728-001" });
    expect(link.getAttribute("href")).toBe("/incidents/INC-2026-0728-001");
  });

  it("shows an empty state when there are no incidents", async () => {
    stubFetch({
      ...analytics,
      total_incidents: 0,
      by_robot: [],
      blockage_hotspots: [],
      daily: [],
      calibration: [],
    });
    render(<AnalyticsPage />);
    expect(
      await screen.findByText("No incidents recorded yet"),
    ).toBeTruthy();
  });

  it("shows measured diagnosis precision from verdicts", async () => {
    render(<AnalyticsPage />);
    expect(await screen.findByText("Diagnosis calibration")).toBeTruthy();
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByText("Sensor dropout ×1")).toBeTruthy();
  });

  it("prompts for verdicts when none exist yet", async () => {
    stubFetch({ ...analytics, calibration: [] });
    render(<AnalyticsPage />);
    expect(
      await screen.findByText(/No engineer verdicts yet/),
    ).toBeTruthy();
  });
});

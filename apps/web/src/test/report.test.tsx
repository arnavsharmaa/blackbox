import { describe, expect, it, vi } from "vitest";
import { Suspense } from "react";
import { render, screen } from "@testing-library/react";
import type { IncidentReport } from "@blackbox/schemas";
import ReportPage from "@/app/incidents/[id]/report/page";
import { testAnalysis, testIncident } from "./fixtures";

const report: IncidentReport = {
  report_version: "1.0",
  incident: {
    id: testIncident.id,
    robot_id: testIncident.robot_id,
    robot_model: testIncident.robot_model,
    facility: testIncident.facility,
    environment: testIncident.environment,
    task_name: testIncident.task_name,
    task_goal: testIncident.task_goal,
    start_time: testIncident.start_time,
    end_time: testIncident.end_time,
    duration_s: 60,
    outcome: testIncident.outcome,
    severity: testIncident.severity,
    software_version: testIncident.software_version,
    map_version: testIncident.map_version,
    summary: testIncident.summary,
    event_count: testIncident.events.length,
  },
  root_cause: {
    category: "persistent_obstacle",
    category_label: "Persistent obstacle blockage",
    confidence: 0.95,
    explanation: testAnalysis.explanation,
    rules_triggered: ["persistent_obstacle_blockage"],
    engine_version: "1.0.0",
  },
  evidence: testAnalysis.evidence,
  recommended_actions: testAnalysis.recommended_actions,
  alternative_causes: testAnalysis.alternative_causes,
  timeline: [
    {
      t: 50,
      timestamp: "2026-07-28T09:00:50Z",
      event_type: "task_timed_out",
      subsystem: "task_manager",
      severity: "error",
      message: "Task timed out",
    },
  ],
  telemetry_summary: [
    { channel: "obstacle_distance", unit: "m", min: 0.42, max: 5, last: 0.42, samples: 3 },
  ],
  reproduction: {
    notes: "Replay incident INC-TEST-100 in BlackBox.",
    replay_url: "/incidents/INC-TEST-100",
  },
  ai_explanation: null,
  markdown: "# Incident Report — INC-TEST-100",
};

describe("Report page", () => {
  it("renders the full report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(report), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    // React's `use()` reads pre-resolved thenables synchronously when they
    // carry status/value, avoiding an act()-unfriendly suspension in jsdom.
    const params = Promise.resolve({ id: "INC-TEST-100" }) as Promise<{
      id: string;
    }> & { status: string; value: { id: string } };
    params.status = "fulfilled";
    params.value = { id: "INC-TEST-100" };

    render(
      <Suspense fallback={<div>suspended</div>}>
        <ReportPage params={params} />
      </Suspense>,
    );

    expect(
      await screen.findByRole("heading", { name: "INC-TEST-100" }),
    ).toBeTruthy();
    expect(
      screen.getByText(/Root cause: Persistent obstacle blockage/),
    ).toBeTruthy();
    expect(
      screen.getByText("Obstacle distance remained below 0.60 m for 30.0 s"),
    ).toBeTruthy();
    expect(screen.getByText("Check the aisle for a stray pallet")).toBeTruthy();
    expect(screen.getByText("Task timed out")).toBeTruthy();
    expect(
      screen.getByText(/Replay incident INC-TEST-100 in BlackBox/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy Markdown" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download JSON" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Print view" })).toBeTruthy();
  });
});

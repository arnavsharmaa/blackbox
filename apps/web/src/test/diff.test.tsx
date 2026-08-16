import { beforeEach, describe, expect, it, vi } from "vitest";
import { Suspense } from "react";
import { render, screen, within } from "@testing-library/react";
import type { DiffResponse, IncidentSummary } from "@blackbox/schemas";
import DiffPage from "@/app/incidents/[id]/diff/page";
import { listResponse, testAnalysis, testIncident, testSummaries } from "./fixtures";

const primarySummary = testSummaries[0] as IncidentSummary;

const baselineSummary: IncidentSummary = {
  ...primarySummary,
  id: "INC-TEST-BASE",
  outcome: "success",
  severity: "info",
  summary: "Baseline run of the same delivery.",
  failure_category: null,
  confidence: null,
};

const baselineIncident = {
  ...testIncident,
  id: "INC-TEST-BASE",
  outcome: "success" as const,
  severity: "info" as const,
};

const diff: DiffResponse = {
  incident: {
    id: testIncident.id,
    robot_id: testIncident.robot_id,
    task_name: testIncident.task_name,
    outcome: "timed_out",
    duration_s: 60,
  },
  baseline: {
    id: "INC-TEST-BASE",
    robot_id: testIncident.robot_id,
    task_name: testIncident.task_name,
    outcome: "success",
    duration_s: 60,
  },
  channels: [
    {
      channel: "obstacle_distance",
      delta_threshold: 0.68,
      max_abs_delta: 4.5,
      max_abs_delta_t: 35,
      first_divergence_t: 20,
    },
    {
      channel: "linear_velocity",
      delta_threshold: 0.12,
      max_abs_delta: 0.8,
      max_abs_delta_t: 45,
      first_divergence_t: 26,
    },
    {
      channel: "localization_confidence",
      delta_threshold: 0.05,
      max_abs_delta: 0.01,
      max_abs_delta_t: 12,
      first_divergence_t: null,
    },
  ],
  first_divergence_t: 20,
  first_divergence_channel: "obstacle_distance",
  events: [
    { event_type: "task_started", incident_count: 1, baseline_count: 1 },
    { event_type: "warning_raised", incident_count: 1, baseline_count: 0 },
    { event_type: "task_timed_out", incident_count: 1, baseline_count: 0 },
  ],
  event_types_only_in_incident: ["warning_raised", "task_timed_out"],
};

function stubRoutes() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("/diff/")) return json(diff);
      if (url.includes("/api/incidents?"))
        return json(listResponse([...testSummaries, baselineSummary]));
      if (url.includes("/INC-TEST-BASE"))
        return json({ incident: baselineIncident, analysis: null });
      if (url.includes("/INC-TEST-100"))
        return json({ incident: testIncident, analysis: testAnalysis });
      throw new Error(`unexpected fetch: ${url}`);
    }),
  );
}

function renderPage() {
  const params = Promise.resolve({ id: "INC-TEST-100" }) as Promise<{
    id: string;
  }> & { status: string; value: { id: string } };
  params.status = "fulfilled";
  params.value = { id: "INC-TEST-100" };
  return render(
    <Suspense fallback={<div>suspended</div>}>
      <DiffPage params={params} />
    </Suspense>,
  );
}

describe("diff page", () => {
  beforeEach(() => {
    stubRoutes();
  });

  it("defaults to the successful same-task run as baseline", async () => {
    renderPage();
    expect(await screen.findByText("Incident comparison")).toBeTruthy();
    const select = (await screen.findByLabelText(
      /Baseline/,
    )) as HTMLSelectElement;
    expect(select.value).toBe("INC-TEST-BASE");
  });

  it("shows the first divergence and links the replay to that moment", async () => {
    renderPage();
    expect(await screen.findByText("First divergence")).toBeTruthy();
    // Shown in both the stat card and the callout sentence.
    expect(screen.getAllByText("20.0 s").length).toBeGreaterThan(0);
    const link = screen.getByRole("link", {
      name: /Open the replay at that moment/,
    });
    expect(link.getAttribute("href")).toBe("/incidents/INC-TEST-100?t=20");
    // Per-channel annotations: diverging and quiet channels.
    expect(screen.getAllByText(/diverges at/).length).toBeGreaterThan(0);
    expect(screen.getByText("no divergence")).toBeTruthy();
  });

  it("marks event types that only occur in the failed run", async () => {
    renderPage();
    const table = (await screen.findByText("Event type")).closest("table");
    expect(table).toBeTruthy();
    const rows = within(table as HTMLTableElement);
    expect(rows.getByText("task timed out")).toBeTruthy();
    expect(rows.getAllByText("only here")).toHaveLength(2);
  });
});

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DiagnosisFeedback } from "@blackbox/schemas";
import { SummaryCard } from "@/components/incident/SummaryCard";
import { testAnalysis, testIncident } from "./fixtures";

function feedbackResponse(
  overrides: Partial<DiagnosisFeedback> = {},
): DiagnosisFeedback {
  return {
    incident_id: testIncident.id,
    verdict: "confirmed",
    diagnosed_category: "persistent_obstacle",
    actual_category: null,
    note: "",
    created_at: "2026-08-16T10:00:00Z",
    ...overrides,
  };
}

function stubFetch(body: DiagnosisFeedback) {
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("diagnosis feedback", () => {
  it("confirms the diagnosis and shows the verdict", async () => {
    const fetchMock = stubFetch(feedbackResponse());
    const user = userEvent.setup();
    render(<SummaryCard incident={testIncident} analysis={testAnalysis} />);

    expect(screen.getByText("Was this diagnosis right?")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /Confirm/ }));

    expect(
      await screen.findByText(/Confirmed by an engineer/),
    ).toBeTruthy();
    // The card also fetches analytics for measured precision — find the
    // feedback POST by URL instead of assuming call order.
    const call = (
      fetchMock.mock.calls as unknown as [string, RequestInit][]
    ).find((c) => String(c[0]).includes("/feedback"))!;
    expect(call).toBeTruthy();
    expect(call[0]).toContain(`/api/incidents/${testIncident.id}/feedback`);
    expect(JSON.parse(String(call[1].body))).toEqual({
      verdict: "confirmed",
    });
  });

  it("corrects the diagnosis with a category and note", async () => {
    const fetchMock = stubFetch(
      feedbackResponse({
        verdict: "corrected",
        actual_category: "sensor_dropout",
        note: "Lidar cable was loose.",
      }),
    );
    const user = userEvent.setup();
    render(<SummaryCard incident={testIncident} analysis={testAnalysis} />);

    await user.click(screen.getByRole("button", { name: /Correct/ }));
    await user.selectOptions(
      screen.getByLabelText(/Actual cause/),
      "sensor_dropout",
    );
    await user.type(
      screen.getByLabelText("Correction note"),
      "Lidar cable was loose.",
    );
    await user.click(screen.getByRole("button", { name: "Save correction" }));

    expect(
      await screen.findByText(/Corrected to Sensor dropout/),
    ).toBeTruthy();
    const call = (
      fetchMock.mock.calls as unknown as [string, RequestInit][]
    ).find((c) => String(c[0]).includes("/feedback"))!;
    expect(JSON.parse(String(call[1].body))).toEqual({
      verdict: "corrected",
      actual_category: "sensor_dropout",
      note: "Lidar cable was loose.",
    });
  });

  it("shows a stored verdict and allows changing it", async () => {
    const user = userEvent.setup();
    render(
      <SummaryCard
        incident={testIncident}
        analysis={testAnalysis}
        initialFeedback={feedbackResponse({ note: "Verified on site." })}
      />,
    );
    expect(screen.getByText(/Confirmed by an engineer/)).toBeTruthy();
    expect(screen.getByText(/Verified on site\./)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Change verdict" }));
    expect(screen.getByRole("button", { name: /Confirm/ })).toBeTruthy();
  });

  it("shows measured precision when calibration data exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const body = String(input).includes("/api/analytics")
          ? {
              calibration: [{
                category: "persistent_obstacle",
                reviewed: 13,
                confirmed: 12,
                precision: 0.9231,
                corrected_to: [],
              }],
            }
          : {};
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    render(<SummaryCard incident={testIncident} analysis={testAnalysis} />);
    expect(await screen.findByText(/Measured precision/)).toBeTruthy();
    expect(screen.getByText("12/13")).toBeTruthy();
    expect(screen.getByText("92%")).toBeTruthy();
  });
});

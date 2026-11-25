import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { RulesResponse } from "@blackbox/schemas";
import RulesPage from "@/app/rules/page";

const rules: RulesResponse = {
  engine_version: "1.0.0",
  diagnosis_threshold: 0.5,
  confidence_ceiling: 0.95,
  rules: [
    {
      rule_id: "sensor_dropout",
      category: "sensor_dropout",
      builtin: true,
      source: "blackbox_api.analysis.rules:rule_sensor_dropout",
      description: "The obstacle sensor went quiet.",
      explanation: "The obstacle sensor stopped publishing.",
      recommended_actions: ["Check lidar power, cabling, and driver logs"],
    },
    {
      rule_id: "acme_battery_sag",
      category: "unknown",
      builtin: false,
      source: "acme_rules:battery_sag",
      description: "Battery voltage sagged under load.",
      explanation: "",
      recommended_actions: [],
    },
  ],
};

describe("rules page", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(rules), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
  });

  it("renders engine meta and each loaded rule", async () => {
    render(<RulesPage />);
    expect(await screen.findByText("Analysis rules")).toBeTruthy();
    // Engine meta line with thresholds.
    expect(screen.getByText("1.0.0")).toBeTruthy();
    expect(screen.getByText(/score at least.*50%/)).toBeTruthy();

    // Built-in rule: category label, source, runbook, badge.
    expect(screen.getByText("Sensor dropout")).toBeTruthy();
    expect(
      screen.getByText("blackbox_api.analysis.rules:rule_sensor_dropout"),
    ).toBeTruthy();
    expect(screen.getByText("built-in")).toBeTruthy();
    expect(
      screen.getByText("Check lidar power, cabling, and driver logs"),
    ).toBeTruthy();

    // Plug-in rule is labeled as such with its source spec.
    expect(screen.getByText("plug-in")).toBeTruthy();
    expect(screen.getByText("acme_rules:battery_sag")).toBeTruthy();

    // Each diagnosable rule links to its filtered incident list.
    const links = screen.getAllByRole("link", {
      name: /Incidents with this diagnosis/,
    });
    expect(
      links.map((a) => a.getAttribute("href")),
    ).toEqual([
      "/?failure_category=sensor_dropout",
      "/?failure_category=unknown",
    ]);
  });
});

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import RobotsPage from "@/app/robots/page";

const analytics = {
  total_incidents: 3,
  critical_incidents: 1,
  total_recovery_attempts: 4,
  categories: [],
  outcomes: [],
  by_robot: [
    {
      robot_id: "W-104",
      robot_model: "Fetchbot AMR-600",
      incidents: 2,
      critical: 1,
      recovery_attempts: 3,
      top_category: "persistent_obstacle",
      last_incident: "2026-08-04",
    },
    {
      robot_id: "W-087",
      robot_model: "Fetchbot AMR-600",
      incidents: 1,
      critical: 0,
      recovery_attempts: 1,
      top_category: null,
      last_incident: "2026-07-29",
    },
  ],
  by_software_version: [],
  blockage_hotspots: [],
  daily: [],
  calibration: [],
  failure_signatures: [],
};

describe("robots page", () => {
  it("lists robots and links to their filtered overview", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify(analytics), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    render(<RobotsPage />);

    const link = await screen.findByRole("link", { name: "W-104" });
    expect(link.getAttribute("href")).toBe("/?robot_id=W-104");
    expect(screen.getByText("Persistent obstacle")).toBeTruthy();
    expect(screen.getByRole("link", { name: "W-087" })).toBeTruthy();
    // No diagnosed category yet renders a placeholder, not a crash.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

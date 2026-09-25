import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SimilarIncidents } from "@/components/incident/SimilarIncidents";
import { testSummaries } from "./fixtures";

function stubFetch(body: unknown) {
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

describe("SimilarIncidents", () => {
  it("renders nothing for a first occurrence", async () => {
    stubFetch([]);
    const { container } = render(
      <SimilarIncidents incidentId="INC-TEST-100" />,
    );
    // Wait a tick for the fetch to settle; the panel must stay absent.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(container.innerHTML).toBe("");
  });

  it("links prior occurrences of the same signature", async () => {
    stubFetch([testSummaries[1]]);
    render(<SimilarIncidents incidentId="INC-TEST-100" />);
    expect(await screen.findByText("This happened before")).toBeTruthy();
    const link = screen.getByRole("link", { name: "INC-TEST-101" });
    expect(link.getAttribute("href")).toBe("/incidents/INC-TEST-101");
    expect(screen.getByText(/W-087/)).toBeTruthy();
  });
});

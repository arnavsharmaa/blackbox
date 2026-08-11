import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UploadPage from "@/app/upload/page";

const SUCCESS = {
  incident_id: "INC-BAG-001",
  event_count: 41,
  telemetry_channels: 7,
  failure_category: "persistent_obstacle",
  confidence: 0.807,
};

describe("upload page", () => {
  it("disables submit until a file is chosen", async () => {
    render(<UploadPage />);
    const button = screen.getByRole("button", { name: "Upload and analyze" });
    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("uploads a file and links to the new incident", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(SUCCESS), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<UploadPage />);

    const input = screen.getByLabelText(/Incident file/);
    await user.upload(
      input,
      new File(["{}"], "incident.json", { type: "application/json" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Upload and analyze" }),
    );

    expect(await screen.findByRole("status")).toBeTruthy();
    expect(
      screen.getByText(/diagnosed/i).textContent,
    ).toContain("Persistent obstacle");
    const link = screen.getByRole("link", { name: /Open INC-BAG-001/ });
    expect(link.getAttribute("href")).toBe("/incidents/INC-BAG-001");

    // The request was a multipart POST to the upload endpoint.
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/incidents/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("renders field-level validation errors from a 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: {
                message: "incident failed schema validation",
                errors: [
                  { field: "robot_id", error: "Field required" },
                  { field: "events", error: "Field required" },
                ],
              },
            }),
            { status: 422 },
          ),
      ),
    );
    const user = userEvent.setup();
    render(<UploadPage />);

    await user.upload(
      screen.getByLabelText(/Incident file/),
      new File(["{}"], "bad.json", { type: "application/json" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Upload and analyze" }),
    );

    const alert = await screen.findByRole("alert");
    expect(
      within(alert).getByText("incident failed schema validation"),
    ).toBeTruthy();
    expect(within(alert).getByText("robot_id")).toBeTruthy();
    expect(within(alert).getByText("events")).toBeTruthy();
  });
});

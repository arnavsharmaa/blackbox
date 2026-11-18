import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IncidentNote } from "@blackbox/schemas";
import { NotesPanel } from "@/components/incident/NotesPanel";

const existing: IncidentNote = {
  id: 1,
  incident_id: "INC-TEST-100",
  text: "Operator confirmed the pallet.",
  author: "arnav",
  created_at: "2026-07-28T10:00:00Z",
};

describe("NotesPanel", () => {
  it("lists notes and adds a new one", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            id: 2,
            incident_id: "INC-TEST-100",
            text: "Linked MNT-4411.",
            author: "",
            created_at: "2026-07-28T11:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <NotesPanel incidentId="INC-TEST-100" initialNotes={[existing]} />,
    );
    expect(screen.getByText("Operator confirmed the pallet.")).toBeTruthy();

    await user.type(screen.getByLabelText("New note"), "Linked MNT-4411.");
    await user.click(screen.getByRole("button", { name: "Add note" }));

    expect(await screen.findByText("Linked MNT-4411.")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toContain("/api/incidents/INC-TEST-100/notes");
    expect(init.method).toBe("POST");
    vi.unstubAllGlobals();
  });

  it("deletes a note", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <NotesPanel incidentId="INC-TEST-100" initialNotes={[existing]} />,
    );
    await user.click(
      screen.getByRole("button", { name: "Delete note 1" }),
    );
    await waitFor(() => {
      expect(
        screen.queryByText("Operator confirmed the pallet."),
      ).toBeNull();
    });
    expect(screen.getByText(/No notes yet/)).toBeTruthy();
    vi.unstubAllGlobals();
  });
});

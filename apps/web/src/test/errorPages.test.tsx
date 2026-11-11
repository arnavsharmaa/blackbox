import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotFound from "@/app/not-found";
import ErrorPage from "@/app/error";

describe("error pages", () => {
  it("404 links back to the overview", () => {
    render(<NotFound />);
    expect(screen.getByText("404")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Back to the incident overview" })
        .getAttribute("href"),
    ).toBe("/");
  });

  it("error boundary shows the message and retries", async () => {
    const reset = vi.fn();
    const user = userEvent.setup();
    render(<ErrorPage error={new Error("kaboom")} reset={reset} />);
    expect(screen.getByRole("alert").textContent).toContain("kaboom");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalled();
  });
});

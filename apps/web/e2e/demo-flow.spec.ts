import { expect, test } from "@playwright/test";

const PRIMARY = "INC-2026-0728-001";

test.describe("demo flow", () => {
  test("overview lists the seeded incidents with diagnoses", async ({
    page,
  }) => {
    await page.goto("/");
    // The failure and its successful baseline share a task name — expect both.
    await expect(
      page.getByRole("link", { name: "Deliver pallet to Loading Bay B" }),
    ).toHaveCount(2);
    await expect(
      page.getByRole("link", { name: "Return to charging dock" }),
    ).toBeVisible();
    // One diagnosis per rule across the four seeded incidents.
    const table = page.getByRole("table");
    await expect(table.getByText("Persistent obstacle")).toBeVisible();
    await expect(table.getByText("Localization failure")).toBeVisible();
    await expect(table.getByText("Controller oscillation")).toBeVisible();
    await expect(table.getByText("Sensor dropout")).toBeVisible();
  });

  test("overview filters narrow the table", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Robot").selectOption("W-104");
    await expect(
      page.getByRole("link", { name: "Deliver pallet to Loading Bay B" }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Return to charging dock" }),
    ).toBeHidden();
  });

  test("replay plays, pauses at the failure moment, and stays synchronized", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}`);
    await expect(page.getByText("Persistent obstacle").first()).toBeVisible();

    const slider = page.getByRole("slider", { name: "Replay position" });
    await expect(slider).toHaveValue("0");

    // Play at 4x: the clock advances in real time.
    await page.getByRole("button", { name: "4×" }).click();
    await page.getByRole("button", { name: "Play replay" }).click();
    await expect
      .poll(async () => Number(await slider.inputValue()), { timeout: 5000 })
      .toBeGreaterThan(1);
    await expect(
      page.getByRole("button", { name: "Pause replay" }),
    ).toBeVisible();

    // Jump straight to the failure moment (t=90 s).
    await page.getByRole("button", { name: "Jump to failure moment" }).click();
    await expect(slider).toHaveValue("90");
    await expect(page.getByText("01:30.0")).toBeVisible();
  });

  test("clicking evidence seeks the replay to its timestamp", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}`);
    await page
      .getByRole("button", { name: /Jump to 31.0 seconds/ })
      .click();
    await expect(
      page.getByRole("slider", { name: "Replay position" }),
    ).toHaveValue("31");
  });

  test("timeline event selection populates the inspector", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}`);
    await page
      .getByRole("button", {
        name: /Obstacle distance 0.52 m below safety threshold/,
      })
      .click();
    const inspector = page.locator("pre").first();
    await expect(inspector).toContainText('"threshold_m": 0.6');
  });

  test("report view renders the evidence-backed root cause", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}/report`);
    await expect(
      page.getByText(/Root cause: Persistent obstacle blockage/),
    ).toBeVisible();
    await expect(
      page.getByText(/consecutive zero-velocity commands/).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Copy Markdown" }),
    ).toBeVisible();
  });

  test("github issue preview builds a complete issue with prefill URL", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}/issue`);
    await expect(
      page.getByRole("heading", { name: /Persistent obstacle blockage/ }),
    ).toBeVisible();
    await expect(page.getByText("## Steps to reproduce")).toBeVisible();

    await page
      .getByPlaceholder("acme/warehouse-robots")
      .fill("acme/warehouse-robots");
    await page.getByRole("button", { name: "Update URL" }).click();
    const prefill = page.getByRole("link", { name: /Open prefilled issue/ });
    await expect(prefill).toHaveAttribute(
      "href",
      /github\.com\/acme\/warehouse-robots\/issues\/new/,
    );
  });
});

test.describe("fleet features", () => {
  test("analytics page shows fleet aggregates", async ({ page }) => {
    await page.goto("/analytics");
    await expect(
      page.getByRole("heading", { name: "Fleet analytics" }),
    ).toBeVisible();
    await expect(page.getByText("Blockage hotspots")).toBeVisible();
    // The seeded persistent-obstacle incident is a hotspot linking to itself.
    await expect(
      page.getByRole("link", { name: PRIMARY }),
    ).toBeVisible();
  });

  test("diff page finds the divergence and deep-links the replay", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}/diff`);
    await expect(
      page.getByRole("heading", { name: "Incident comparison" }),
    ).toBeVisible();
    // The successful same-task run is preselected as the baseline.
    await expect(page.getByLabel("Baseline")).toHaveValue(
      "INC-2026-0721-BASE",
    );
    // Clearance diverges at t=20 when the failed run's lidar sees the pallet.
    await expect(page.getByText("First divergence")).toBeVisible();
    await expect(page.getByText("20.0 s").first()).toBeVisible();
    await expect(page.getByText(/only here/i).first()).toBeVisible();

    // The callout deep-links into the replay at the divergence moment.
    await page
      .getByRole("link", { name: /Open the replay at that moment/ })
      .click();
    await expect(
      page.getByRole("slider", { name: "Replay position" }),
    ).toHaveValue("20");
  });

  test("confirming a diagnosis feeds the calibration table", async ({
    page,
  }) => {
    await page.goto(`/incidents/${PRIMARY}`);
    await page.getByRole("button", { name: /Confirm/ }).click();
    await expect(page.getByText(/Confirmed by an engineer/)).toBeVisible();

    await page.goto("/analytics");
    await expect(page.getByText("Diagnosis calibration")).toBeVisible();
    const calibrationRow = page
      .getByRole("row")
      .filter({ hasText: "Persistent obstacle" })
      .filter({ hasText: "100%" });
    await expect(calibrationRow.first()).toBeVisible();
  });

  test("upload page rejects malformed json with field errors", async ({
    page,
  }) => {
    await page.goto("/upload");
    await page.getByLabel(/Incident file/).setInputFiles({
      name: "bad.json",
      mimeType: "application/json",
      buffer: Buffer.from("{not valid json"),
    });
    await page.getByRole("button", { name: "Upload and analyze" }).click();
    // Scope to our alert: Next.js's route announcer also has role="alert".
    await expect(
      page.getByRole("alert").filter({ hasText: /not valid JSON/ }),
    ).toBeVisible();
  });
});

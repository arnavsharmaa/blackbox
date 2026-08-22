import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchIncidents } from "@/lib/api";
import { listResponse } from "./fixtures";

function stubFetch() {
  const fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify(listResponse()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("api token header", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("omits Authorization when no token is configured", async () => {
    const fetchMock = stubFetch();
    await fetchIncidents();
    const [, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(
      (init.headers as Record<string, string>).Authorization,
    ).toBeUndefined();
  });

  it("sends the configured token as a bearer header", async () => {
    vi.stubEnv("NEXT_PUBLIC_BLACKBOX_API_TOKEN", "sekret-1");
    const fetchMock = stubFetch();
    await fetchIncidents();
    const [, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer sekret-1",
    );
  });
});

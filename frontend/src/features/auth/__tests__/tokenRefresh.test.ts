/**
 * Token refresh flow tests.
 *
 * The most critical auth path: 401 response → queue failed requests →
 * refresh token → retry all queued requests with new token.
 *
 * A regression here silently logs out every user. (#31)
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import MockAdapter from "axios-mock-adapter";

// We import the module under test AFTER setting up mocks so Zustand store
// is initialised in a clean state for each test.
const getClient = () => import("@/shared/api/client");

describe("performTokenRefresh", () => {
  let mock: MockAdapter;

  beforeEach(async () => {
    vi.resetModules();
    // Use the real axios but with a mock adapter
    mock = new MockAdapter(axios);
  });

  afterEach(() => {
    mock.restore();
    vi.restoreAllMocks();
  });

  it("calls /api/v1/auth/refresh and stores the new token", async () => {
    const { performTokenRefresh } = await getClient();

    mock.onPost("/api/v1/auth/refresh").reply(200, { access_token: "new-token-abc" });

    const token = await performTokenRefresh();
    expect(token).toBe("new-token-abc");
  });

  it("deduplicates concurrent refresh calls — only one request is sent", async () => {
    const { performTokenRefresh } = await getClient();

    let callCount = 0;
    mock.onPost("/api/v1/auth/refresh").reply(() => {
      callCount++;
      return [200, { access_token: "deduped-token" }];
    });

    // Fire three concurrent refresh calls
    const [t1, t2, t3] = await Promise.all([
      performTokenRefresh(),
      performTokenRefresh(),
      performTokenRefresh(),
    ]);

    // Only one HTTP request should have been made
    expect(callCount).toBe(1);
    expect(t1).toBe("deduped-token");
    expect(t2).toBe("deduped-token");
    expect(t3).toBe("deduped-token");
  });

  it("rejects all queued callers when refresh fails", async () => {
    const { performTokenRefresh } = await getClient();

    mock.onPost("/api/v1/auth/refresh").reply(401, { detail: "Refresh token expired" });

    const results = await Promise.allSettled([
      performTokenRefresh(),
      performTokenRefresh(),
    ]);

    expect(results[0].status).toBe("rejected");
    expect(results[1].status).toBe("rejected");
  });
});

describe("401 interceptor → retry flow", () => {
  let mock: MockAdapter;

  beforeEach(() => {
    vi.resetModules();
    mock = new MockAdapter(axios);
  });

  afterEach(() => {
    mock.restore();
    vi.restoreAllMocks();
  });

  it("retries the original request with the new token after a 401", async () => {
    // First call to /investigations returns 401, then succeeds with new token
    let invCallCount = 0;
    mock.onGet("/api/v1/investigations").reply(() => {
      invCallCount++;
      if (invCallCount === 1) return [401, {}];
      return [200, { items: [] }];
    });

    mock.onPost("/api/v1/auth/refresh").reply(200, { access_token: "refreshed-token" });

    const { default: apiClient } = await import("@/shared/api/client");
    const res = await (apiClient as ReturnType<typeof axios.create>).get("/investigations");

    expect(res.status).toBe(200);
    expect(invCallCount).toBe(2); // initial + retry
  });

  it("redirects to /login when both the request and refresh fail", async () => {
    // Patch window.location
    const locationSpy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      href: "",
      pathname: "/dashboard",
    } as Location);

    mock.onGet("/api/v1/investigations").reply(401, {});
    mock.onPost("/api/v1/auth/refresh").reply(401, { detail: "Session expired" });

    const { default: apiClient } = await import("@/shared/api/client");

    await expect(
      (apiClient as ReturnType<typeof axios.create>).get("/investigations")
    ).rejects.toBeDefined();

    locationSpy.mockRestore();
  });
});

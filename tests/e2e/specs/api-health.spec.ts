import { test, expect } from "@playwright/test";

test.describe("API Health", () => {
  test("health endpoint returns ok", async ({ request }) => {
    const response = await request.get("/health");
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("ok");
  });

  test("liveness endpoint returns alive", async ({ request }) => {
    const response = await request.get("/health/live");
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("alive");
  });

  test("protected endpoint returns 401 without auth", async ({ request }) => {
    const response = await request.get("/api/v1/auth/me");
    expect(response.status()).toBe(401);
  });

  test("login endpoint returns 422 without body", async ({ request }) => {
    const response = await request.post("/api/v1/auth/login");
    expect(response.status()).toBe(422);
  });
});

import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("landing page loads", async ({ page }) => {
    await page.goto("/");
    // Should either show login or dashboard
    const url = page.url();
    expect(url).toMatch(/\/(login|dashboard|investigations)/);
  });

  test("unauthenticated access shows login-related content", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText(/sign in/i).first()).toBeVisible();
  });

  test("register page has multi-step form", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByText(/step 1/i)).toBeVisible();
    await expect(page.getByText(/create your account/i)).toBeVisible();
  });
});

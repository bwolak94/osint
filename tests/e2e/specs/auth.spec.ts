import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";

test.describe("Authentication", () => {
  test("login page renders correctly", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.submitButton).toBeVisible();
    await expect(loginPage.registerLink).toBeVisible();
  });

  test("shows error with empty form submission", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.submitButton.click();
    // Form validation should prevent submission
    await expect(loginPage.emailInput).toBeFocused();
  });

  test("register link navigates to register page", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.registerLink.click();
    await page.waitForURL("**/register**");
    await expect(page.getByText(/create your account/i)).toBeVisible();
  });

  test("forgot password link works", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: /forgot/i }).click();
    await page.waitForURL("**/forgot-password**");
    await expect(page.getByText(/reset password/i)).toBeVisible();
  });
});

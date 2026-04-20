import { type Page, type Locator, expect } from "@playwright/test";

export class InvestigationsPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly newButton: Locator;
  readonly searchInput: Locator;
  readonly investigationCards: Locator;
  readonly emptyState: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: /investigations/i });
    this.newButton = page.getByRole("button", { name: /new investigation/i });
    this.searchInput = page.getByPlaceholder(/search/i);
    this.investigationCards = page.locator("[class*='cursor-pointer']");
    this.emptyState = page.getByText(/no investigations/i);
  }

  async goto() {
    await this.page.goto("/investigations");
  }

  async expectVisible() {
    await expect(this.heading).toBeVisible();
  }

  async clickNewInvestigation() {
    await this.newButton.click();
  }

  async search(query: string) {
    await this.searchInput.fill(query);
  }

  async clickFirstInvestigation() {
    await this.investigationCards.first().click();
  }
}

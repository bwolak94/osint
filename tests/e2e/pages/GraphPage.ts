import { type Page, type Locator, expect } from "@playwright/test";

export class GraphPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly toolbar: Locator;
  readonly canvas: Locator;
  readonly legend: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: /knowledge graph/i });
    this.toolbar = page.locator("[class*='gap-2']").first();
    this.canvas = page.locator(".react-flow");
    this.legend = page.getByText(/person/i);
  }

  async goto(investigationId: string) {
    await this.page.goto(`/investigations/${investigationId}/graph`);
  }

  async expectVisible() {
    await expect(this.heading).toBeVisible();
  }
}

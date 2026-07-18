import { Page, Locator, expect } from '@playwright/test';

export class PipelinePage {
  readonly page: Page;
  readonly newItemButton: Locator;
  readonly searchInput: Locator;
  readonly priorityFilter: Locator;
  readonly stageFilter: Locator;
  readonly workflowButton: Locator;
  readonly createModal: Locator;

  constructor(page: Page) {
    this.page = page;
    // Live UI: the header button that opens the create modal is labeled "New Idea"
    // (the per-column "+ Add idea" buttons do not open the modal).
    this.newItemButton = page.getByRole('button', { name: 'New Idea' });
    this.searchInput = page.getByPlaceholder('Search ideas...');
    this.priorityFilter = page.locator('select').filter({ hasText: 'All Priorities' });
    this.stageFilter = page.locator('select').filter({ hasText: 'All Stages' });
    this.workflowButton = page.getByRole('button', { name: 'How it works' });
    this.createModal = page.locator('div').filter({ hasText: 'Create New Idea' });
  }

  async goto() {
    await this.page.goto('/pipeline');
  }

  async createIdea(id: string, title: string) {
    await this.newItemButton.click();
    // Live create modal (overlay `.fixed.inset-0`). Required fields in order:
    // Item ID (placeholder "e.g. IDEA-1"), Title (placeholder-less 2nd text input),
    // Core Goal (textarea, placeholder "e.g. Summarize all errors in the logs...").
    // No label[for]/aria-label wiring on these inputs, so scope positionally.
    // Submit button is "Create" (was "Create Item" when the spec was written).
    const modal = this.page.locator('.fixed.inset-0');
    await modal.locator('input[placeholder="e.g. IDEA-1"]').fill(id);
    await modal.locator('input[type="text"]').nth(1).fill(title);
    await modal.getByPlaceholder('e.g. Summarize all errors in the logs...').first().fill(title);
    await modal.getByRole('button', { name: 'Create' }).click();
  }

  async searchIdeas(query: string) {
    await this.searchInput.fill(query);
  }

  async getCardByTitle(title: string) {
    // Scope to the live card class (`group relative bg-white p-4 … cursor-grab
    // hover-lift …`). The previous `div.filter({ hasText: title }).first()` matched
    // <div id="root"> (whole app) — too loose for substring assertions.
    return this.page.locator('.cursor-grab.hover-lift').filter({ hasText: title }).first();
  }

  // The live board does NOT render the stage name inside a card — the stage is
  // shown in the column header (`h2`). To assert a card "is in INTAKE", ask which
  // column the card lives under (nearest column-wrapping ancestor's `h2` text).
  async cardColumnHeader(title: string) {
    const card = await this.getCardByTitle(title);
    return card
      .locator('xpath=ancestor::div[contains(@class,"min-w-[240px]")]')
      .locator('h2')
      .first();
  }

  async openEditor(title: string) {
    const card = await this.getCardByTitle(title);
    await card.click();
  }

  async deleteItem() {
    await this.page.getByRole('button', { name: 'Delete Item' }).click();
    // Handle the native window.confirm dialog
    await this.page.once('dialog', dialog => dialog.accept());
  }

  async getColumnByTitle(title: string) {
    return this.page.locator('h2', { hasText: title }).first();
  }
}
